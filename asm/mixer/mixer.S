; Mixer Mode M1 (docs/mixer-mode-plan.md): the bus engine with a fixed test
; layout, MS-70CDR 2.10 OS. Test builds only, until M2.
;
; Replaces the stock slot loop (packet 0x1181BE00 jumps here, chain_jump.S).
; The stock loop calls slots 0-5 in order on one shared stereo buffer F
; (ctx[5], 0x11F03738, LLLLLLLL RRRRRRRR float32; every effect works in place).
; This runs the same calls, grouped by bus (docs/mixer-mode-m0.md, "Bus B"):
;   1. the PRE slots on F
;   2. copy F -> S (the split point)
;   3. the BUS A slots on F, copy F -> A
;   4. copy S -> F, the BUS B slots on F (F is now bus B)
;   5. F = 0.5 x A + 0.5 x F (MIX), then the POST slots on F
; and goes on at 0x1181BE48 (the stock post mix), as the stock loop does.
; Within a bus, slots run in index order (0 first, the rightmost on screen).
; F is swapped by content, never by pointer: two OS slot functions (mute,
; gain) hard-code 0x11F03738. Acc (ctx[6]) and Dry (ctx[4]) stay shared.
; A 50/50 sum is never louder than the louder bus, and out_to_int clips at
; +-1.0, so M1 has no limiter. ponytail: add the safety limiter in M2, when
; the MIX levels can go above 0.5.
;
; Registers: the block's register save (0xC00E14C0) ran before this, so the
; callee-saved A10-A15 / B10-B13 are free; effects keep them (C ABI).
;   A11 bus being run, A12 slot, B10 return from run_bus.
;
; Loaded in DDR at 0xC00F6000 (MOD code area, after the probe section that
; ends at 0xC00F53C0). Bus table at +32 (one byte per slot, 0 PRE, 1 BUS A,
; 2 BUS B, 3 POST): the layout patches rewrite those 6 bytes.

        .equ    BASE, 0xC00F6000
        .equ    LAYOUT, BASE + 32
        .equ    AFTER_LOOP, 0x1181BE48      ; stock: callp 0x1181B090 (post mix)
        .equ    FX_TABLE, 0xC00EE930        ; audio function of each slot
        .equ    STATE0, 0x11F03000          ; slot state blocks, 212 B each
        .equ    SLOT_VAR, 576               ; B14 offset: slot being run
        .equ    BUF_F, 0x11F03738           ; ctx[5] chain signal, 16 floats
        .equ    BUF_S, 0x11F03B80           ; split copy (free L1D, M0)
        .equ    BUF_A, 0x11F03BC0           ; bus A result
        .equ    HALF, 0x3F000000            ; 0.5f
        .equ    PRE, 0
        .equ    BUS_A, 1
        .equ    BUS_B, 2
        .equ    POST, 3

        .text
        .nocmp
vectors:
        b       .S2     engine              ; +0 from 0x1181BE00
        nop     5
        .word   0, 0, 0, 0, 0, 0            ; nops: rest of the packet
layout:                                     ; +32, never executed
        .byte   PRE, PRE, BUS_A, BUS_B, POST, POST
        .byte   0, 0
        .word   0, 0, 0, 0, 0, 0

engine:
        mvk     .L1     PRE, a11
        b       .S1     run_bus
        addkpc  .S2     e_split, b10, 4
e_split:
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mvkl    .S1     BUF_S, a5
        mvkh    .S1     BUF_S, a5
        callp   .S2     copy16, b3          ; F -> S
        mvk     .L1     BUS_A, a11
        b       .S1     run_bus
        addkpc  .S2     e_a, b10, 4
e_a:
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mvkl    .S1     BUF_A, a5
        mvkh    .S1     BUF_A, a5
        callp   .S2     copy16, b3          ; F -> A
        mvkl    .S1     BUF_S, a4
        mvkh    .S1     BUF_S, a4
        mvkl    .S1     BUF_F, a5
        mvkh    .S1     BUF_F, a5
        callp   .S2     copy16, b3          ; S -> F
        mvk     .L1     BUS_B, a11
        b       .S1     run_bus
        addkpc  .S2     e_mix, b10, 4
e_mix:
        mvkl    .S1     BUF_A, a4
        mvkh    .S1     BUF_A, a4
        mvkl    .S1     BUF_F, a5
        mvkh    .S1     BUF_F, a5
        mvkl    .S1     HALF, a6
        mvkh    .S1     HALF, a6
        mvk     .S1     16, a1
mx_loop:
        ldw     .D1T1   *a4++, a2           ; A
        ldw     .D1T1   *a5, a3             ; B
        nop     4
        addsp   .L1     a2, a3, a2
        nop     3
        mpysp   .M1     a2, a6, a2
        nop     3
        stw     .D1T1   a2, *a5++           ; F = 0.5 x (A + B)
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     mx_loop
        nop     5
        mvk     .L1     POST, a11
        b       .S1     run_bus
        addkpc  .S2     e_out, b10, 4
e_out:
        mvk     .L2     6, b0
        stw     .D2T2   b0, *+b14(SLOT_VAR) ; as the stock loop leaves it
        mvkl    .S2     AFTER_LOOP, b0
        mvkh    .S2     AFTER_LOOP, b0
        b       .S2     b0
        nop     5

; Every slot whose bus is A11, in slot order, the way the stock loop calls
; it (B14+576 = slot, A4 = slot state, call 0xC00EE930[slot]). Returns to B10.
run_bus:
        mvk     .L1     0, a12
rb_slot:
        mvkl    .S1     LAYOUT, a0
        mvkh    .S1     LAYOUT, a0
        ldbu    .D1T1   *+a0[a12], a0
        nop     4
        cmpeq   .L1     a0, a11, a1
  [!a1] b       .S1     rb_next
        nop     5
        stw     .D2T1   a12, *+b14(SLOT_VAR)
        mvk     .S1     212, a0
        mpy     .M1     a0, a12, a1
        mvkl    .S1     STATE0, a4
        mvkh    .S1     STATE0, a4
        add     .L1     a4, a1, a4          ; A4 = state of the slot
        mvkl    .S2     FX_TABLE, b5
        mvkh    .S2     FX_TABLE, b5
        mv      .L2X    a12, b6
        ldw     .D2T2   *+b5[b6], b4        ; B4 = its audio function
        nop     4
        b       .S2     b4
        addkpc  .S2     rb_next, b3, 4
rb_next:
        add     .L1     1, a12, a12
        cmpgt   .L1     6, a12, a0
  [a0]  b       .S1     rb_slot
        nop     5
        b       .S2     b10
        nop     5

; 16 words from A4 to A5 (both 8-byte aligned). Uses A1-A5. Returns to B3.
copy16:
        mvk     .L1     8, a1
cp_loop:
        lddw    .D1T1   *a4++, a3:a2
        nop     4
        stdw    .D1T1   a3:a2, *a5++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     cp_loop
        nop     5
        b       .S2     b3
        nop     5
