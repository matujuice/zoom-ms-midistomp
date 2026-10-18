; Mixer Mode M3a (docs/mixer-mode-plan.md), MS-70CDR 2.10 OS. Test builds only.
;
; The bus engine of M1 plus the node settings, saved per patch:
;   IN      Input Level
;   [ROUTE] Send (A <-> B, centre = both full), Mode (Serial / Parallel),
;           Bus A Level, Bus B Level
;   [MIX]   Crossfade (A <-> B), Curve (Smooth / DJ / Cut),
;           Bus A Level, Bus B Level, Phase Invert B
;   OUT     Master, and a LIMIT tag while the limiter cuts (poll)
;   BUS     the bus of each slot (PRE / A / B / POST), no CC
; on the MIXER screen (menu entry 5, screen 15) and on MIDI CC 85-95. Levels
; go 0-150, 100 = unity.
;
; Engine (replaces the stock slot loop: packet 0x1181BE00 jumps to +0,
; chain_jump.S). The stock loop calls slots 0-5 in order on one shared stereo
; buffer F (ctx[5], 0x11F03738, LLLLLLLL RRRRRRRR float32, effects work in
; place). Both modes start with F x Input Level. Serial then does the same.
; Parallel runs the same calls by bus:
;   1. the PRE slots on F, S = F (the split point)
;   2. F = SendA x RouteA x S, the BUS A slots, A = F
;   3. F = SendB x RouteB x S, the BUS B slots
;   4. F = cA x A + cB x F, cA/cB = curve x Mix level (x -1 Phase B)
;   5. the POST slots
; Both modes end with F x Master, then the safety limiter, and go on at
; 0x1181BE48 (the stock post mix). Gains are recomputed every
; block and smoothed (g += (target - g) / 4), so knob and CC moves don't step.
; F is swapped by content, never by pointer: two OS slot functions (mute,
; gain) hard-code 0x11F03738.
;
; Bus of each slot (M3a): LAYOUT[slot], saved with the patch, set on the
; MIXER screen's BUS pages (temporary, until M3b's Effect Chain screen). It
; follows the effect when the stock Effect Chain screen moves it (mv_swap),
; or an effect is added (mv_add) or deleted (mv_delete): each wraps the stock
; function at its only call site and moves the buses just before stock moves
; the effects (docs/mixer-mode-m3-research.md, "M3a hooks"). The routing
; probe ZDL still writes 0x80 | bus into MAIL[slot] every block; at the end
; of the block the engine copies it into LAYOUT and clears MAIL.
;
; Saving (route A, docs/mixer-mode-m0.md "M0b"): the 12 setting bytes (11 +
; MAGIC) ride in bytes 14 and 15 of the six 18-byte slot blocks of the packed
; 122-byte patch, the high bits of the 28-bit P8 field (knob 8 never goes
; above 4095); each slot's bus rides in byte 17 of its block (bits 0-1,
; bits 2-7 kept 0 for M3c), which stock packs as 0 and never unpacks. LIVE
; holds the 12 bytes of the patch being played and LAYOUT (right after it)
; its buses, SAVED + its 6 buses the ones stored in flash (IS_DIRTY compares
; them, as stock compares the patch with its saved copy at 0xC009C07C).
;   - unpack_live (patch load into 0xC009BF58) / unpack_saved (the saved
;     copy, 0xC009C07C): stock unpack, take the bytes, mask P8 to 12 bits.
;   - rec_save (every patch record save, 0xC00B84C0): when the buffer is the
;     live-save one (0xC009C2A8, the live patch packed by 0xC00B84D0), put
;     LIVE in and SAVED = LIVE. Other saves (copies, editor store, factory
;     reset) are packed records that carry their own bytes. A patch load
;     that auto saves the patch it leaves (0xC00B89F4, after the unpack)
;     gets PREV, the settings LIVE had before the unpack; unpack_live
;     sets that save up for mixer-only edits too.
;   - pack_dump (the patch sent to an editor): stock pack, put LIVE in.
;   - dirty (IS_DIRTY): stock, or LIVE differs from SAVED.
; The 18 bytes (12 + 6 buses) travel together through all of these.
; A patch without MAGIC (stock, v1.x, factory) loads the defaults: Serial,
; every slot PRE.
;
; Registers in the engine: the block's register save (0xC00E14C0) ran
; before this, so A10-A15 / B10-B13 are free (effects keep them, C ABI).
;   A11 bus being run, A12 slot, B10 return from run_bus, B13 bus mask
;   (0 in Serial: every slot matches PRE), A13-A15 / B11 in gains_update.

        .equ    BASE, 0xC00F6000
        .equ    MASTER, BASE + 72           ; Master, smoothed (float)
        .equ    PEND, BASE + 76             ; 1: the load's auto save gets PREV
        .equ    LIMHIT, BASE + 77           ; 1: the limiter cut the gain (poll clears)
        .equ    SHOWN, BASE + 78            ; LIMIT tag as last drawn
        .equ    HOLD, BASE + 80             ; polls left to show LIMIT
        .equ    PAGE, BASE + 128            ; MIXER screen page 0-7
        .equ    MAIL, BASE + 136            ; [6] routing probe ZDL: 0x80 | bus
        .equ    LIVE, BASE + 144            ; [12] settings of the patch played
        .equ    LAYOUT, BASE + 156          ; [6] ... and the bus of each slot (setting 12-17)
        .equ    SAVED, BASE + 162           ; [12 + 6] ... as saved in flash
        .equ    PREV, BASE + 180            ; [12 + 6] LIVE before a patch load
        .equ    MENU6, BASE + 200           ; menu entry names
        .equ    GAINS, BASE + 224           ; In, SendA, SendB, cA, cB, limiter
        .equ    MAXES, BASE + 248           ; [18] maximum of each setting
        .equ    DEFAULTS, BASE + 266        ; [18]
        .equ    PAGES, BASE + 284           ; [8][4] setting under knob 1-3

        .equ    AFTER_LOOP, 0x1181BE48      ; stock: callp 0x1181B090 (post mix)
        .equ    FX_TABLE, 0xC00EE930        ; audio function of each slot
        .equ    STATE0, 0x11F03000          ; slot state blocks, 212 B each
        .equ    SLOT_VAR, 576               ; B14 offset: slot being run
        .equ    BUF_F, 0x11F03738           ; ctx[5] chain signal, 16 floats
        .equ    BUF_S, 0x11F03B80           ; split copy (free L1D, M0)
        .equ    BUF_A, 0x11F03BC0           ; bus A result
        .equ    PRE, 0
        .equ    BUS_A, 1
        .equ    BUS_B, 2
        .equ    POST, 3

        .equ    UNPACK_WRAP, 0xC00B8294     ; (RAM patch, packed)
        .equ    PACK_WRAP, 0xC00B8474       ; (packed, RAM patch)
        .equ    IS_DIRTY, 0xC00B8534        ; -> 1 = patch differs from saved
        .equ    REC_SAVE, 0xC00B49F4        ; (record, buffer)
        .equ    SAVE_BUF, 0xC009C2A8        ; live patch, packed for saving
        .equ    LIVE_PATCH, 0xC009BF58      ; the patch played, unpacked
        .equ    MEMCPY, 0xC00E09C0          ; (dst, src, n)
        .equ    FX_SWAP, 0xC00B6BC4         ; (row, row) Effect Chain move
        .equ    FX_ADD, 0xC00C22F4          ; (effect id) insert at ANCHOR + SIDE
        .equ    FX_DELETE, 0xC00C2030       ; delete the slot under the cursor
        .equ    COUNT, 0xC009C068           ; number of effects in the patch
        .equ    VIEW, 0xC009D8F8            ; play-mode view (word)
        .equ    CURSOR, 0xC009C064          ; play-mode cursor (signed byte)
        .equ    CURSOR_SLOTS, 0xC00EE748    ; [view][6] slot under each cursor position
        .equ    ANCHOR, 128                 ; B14 offsets: the slot an add goes next to,
        .equ    SIDE, 132                   ; 1: on its left (slot + 1)
        .equ    SET_SCREEN, 0xC00A75E0      ; (screen, row)
        .equ    KEY_DONE, 0xC00A83C0        ; key dispatcher epilogue, A4 = redraw
        .equ    DRAW_DONE, 0xC00A9404       ; draw dispatcher epilogue
        .equ    DRAW_TITLE, 0xC00A7378      ; (string)
        .equ    DRAW_TEXT, 0xC009FCE0       ; (0, string, x, y)
        .equ    SOFTKEY, 0xC009F8F0         ; (knob, string, 0)
        .equ    SNPRINTF, 0xC00DDEE0        ; (buf, size, fmt on stack +4, ...)
        .equ    STR_EXIT, 0xC00E90FC
        .equ    STR_BLANK, 0xC00E9101
        .equ    STEP, 0xC00F2020            ; midi_cc step.S: CC 80/81, then stock
        .equ    UI_REFRESH, 0xC00ACD84
        .equ    POLL, 0x1181E800            ; midi_clock poll.S (L2)
        .equ    MODE, 320                   ; B14 offsets: 11 = menu
        .equ    SCREEN, 352                 ; 15 = MIXER
        .equ    HOLD_POLLS, 30              ; LIMIT stays about 0.5 s
        .equ    EVENT_POST, 0xC00CBF40
        .equ    UI_EVENT_OFS, 656           ; B14 offset
        .equ    EV_ENTER, 34                ; knob 1 press
        .equ    EV_EXIT, 65                 ; knob 2 release
        .equ    EV_TURN, 160                ; 160-162 knob 1-3 turn, A5 = steps
        .equ    CC_FIRST, 85                ; CC 85-95

        .equ    S_MODE, 0                   ; setting bytes
        .equ    S_SEND, 1
        .equ    S_IN, 2
        .equ    S_RA, 3
        .equ    S_RB, 4
        .equ    S_XF, 5
        .equ    S_MASTER, 6
        .equ    S_CURVE, 7                  ; 0 Smooth, 1 DJ, 2 Cut
        .equ    S_MA, 8
        .equ    S_MB, 9
        .equ    S_PHASE, 10
        .equ    MAGIC, 0x4D                 ; byte 11: settings are present
        .equ    S_BUS, 12                   ; 12-17: LAYOUT, the bus of slot 0-5
        .equ    S_LAST, 17
        .equ    NONE, 255

        .equ    F_001, 0x3C23D70A           ; 0.01f
        .equ    F_ONE, 0x3F800000
        .equ    F_TWO, 0x40000000
        .equ    F_HALF, 0x3F000000
        .equ    F_QUARTER, 0x3E800000
        .equ    F_ONE5, 0x3FC00000          ; 1.5f
        .equ    F_CEIL, 0x3F7AE148          ; 0.98f, limiter ceiling
        .equ    F_REL, 0x3A83126F           ; 0.001f per block, limiter release

        .text
        .nocmp
; +0: entry points at fixed offsets (the patch file names them by address)
vectors:
        b       .S2     engine              ; +0  from 0x1181BE00
        nop     5
        b       .S2     unpack_live         ; +8  callp at 0xC00B8964
        nop     5
        b       .S2     unpack_saved        ; +16 callp at 0xC00AE2EC
        nop     5
        b       .S2     pack_dump           ; +24 callp at 0xC00AE680
        nop     5
        b       .S2     dirty               ; +32 callp at 4 IS_DIRTY sites
        nop     5
        b       .S2     rec_save            ; +40 jump from 0xC00B84C0
        nop     5
        b       .S2     keys_e              ; +48 screen 15 key table
        nop     5
        b       .S2     draw_e              ; +56 screen 15 draw table
        nop     5
        b       .S2     cc                  ; +64 midi_cc handler.S: CCs not 14-73
        nop     5
        .word   0, 0, 0                     ; +72 MASTER, PEND / LIMHIT / SHOWN, HOLD
        .word   0, 0, 0
        b       .S2     mv_swap             ; +96  callp at 0xC00B76A4 (FX_SWAP)
        nop     5
        b       .S2     mv_add              ; +104 callp at 0xC00A7BE0 (FX_ADD)
        nop     5
        b       .S2     mv_delete           ; +112 callp at 0xC00A8294 (FX_DELETE)
        nop     5
        b       .S2     poll                ; +120 jump from midi-clock's poll trampoline
        nop     5

; +128: data at fixed offsets (the .equ above), never executed
        .word   0, 0                        ; +128 PAGE
        .byte   0, 0, 0, 0, 0, 0, 0, 0      ; +136 MAIL
        .byte   0, 50, 100, 100, 100, 50, 100, 1, 100, 100, 0, MAGIC ; +144 LIVE
        .byte   PRE, PRE, PRE, PRE, PRE, PRE ; +156 LAYOUT
        .byte   0, 50, 100, 100, 100, 50, 100, 1, 100, 100, 0, MAGIC ; +162 SAVED
        .byte   PRE, PRE, PRE, PRE, PRE, PRE
        .byte   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ; +180 PREV
        .byte   0, 0
        ; +200 MENU6: the five menu entries (midi_settings.S) with MIXER
        ; before the version entry
        .word   0xC00E8FE4, 0xC00E8FF7, 0xC00E9004, 0x1181EC63, s_mixer, 0xC00E900D
        .word   0, 0, 0, 0, 0, F_ONE        ; +224 GAINS
        .byte   1, 100, 150, 150, 150, 100, 150, 2, 150, 150, 1, 255 ; +248 MAXES
        .byte   3, 3, 3, 3, 3, 3
        .byte   0, 50, 100, 100, 100, 50, 100, 1, 100, 100, 0, MAGIC ; +266 DEFAULTS
        .byte   PRE, PRE, PRE, PRE, PRE, PRE
        ; +284 PAGES: IN, ROUTE 1/2, ROUTE 2/2, MIX 1/2, MIX 2/2, OUT, BUS 1/2,
        ; BUS 2/2 (S1 = slot 0, the rightmost effect)
        .byte   S_IN, NONE, NONE, NONE
        .byte   S_SEND, NONE, S_MODE, NONE, S_RA, S_RB, NONE, NONE
        .byte   S_XF, NONE, S_CURVE, NONE, S_MA, S_MB, S_PHASE, NONE
        .byte   S_MASTER, NONE, NONE, NONE
        ; ponytail: BUS 1/2 and 2/2 are a test UI until M3b's Effect Chain
        ; screen sets buses; no CC for buses (M3b decides)
        .byte   S_BUS, S_BUS + 1, S_BUS + 2, NONE, S_BUS + 3, S_BUS + 4, S_BUS + 5, NONE
        .byte   0, 0, 0, 0                  ; to +320

; ---------------------------------------------------------------- engine

engine:
        mvk     .L1     S_IN, a4            ; the chain's start, both modes: Input Level
        callp   .S2     pct, b3
        mvkl    .S1     GAINS, a5
        mvkh    .S1     GAINS, a5
        callp   .S2     smooth, b3
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mv      .L1     a4, a5
        callp   .S2     scale16, b3         ; A6 = the smoothed Input Level
        mvkl    .S1     LIVE, a3
        mvkh    .S1     LIVE, a3
        ldbu    .D1T2   *+a3(S_MODE), b0
        nop     4
        mvk     .L2     0, b13              ; Serial: every slot is PRE
  [b0]  mvk     .L2     3, b13              ; Parallel: the layout's bus
  [!b0] b       .S1     serial
        nop     5
        callp   .S2     gains_update, b3
        mvk     .L1     PRE, a11
        b       .S1     run_bus
        addkpc  .S2     e_split, b10, 4
e_split:
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mvkl    .S1     BUF_S, a5
        mvkh    .S1     BUF_S, a5
        callp   .S2     copy16, b3          ; S = F
        mvkl    .S1     BUF_S, a4
        mvkh    .S1     BUF_S, a4
        mvkl    .S1     BUF_F, a5
        mvkh    .S1     BUF_F, a5
        mvkl    .S1     GAINS, a7
        mvkh    .S1     GAINS, a7
        ldw     .D1T1   *+a7(4), a6         ; SendA x RouteA
        nop     4
        callp   .S2     scale16, b3
        mvk     .L1     BUS_A, a11
        b       .S1     run_bus
        addkpc  .S2     e_a, b10, 4
e_a:
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mvkl    .S1     BUF_A, a5
        mvkh    .S1     BUF_A, a5
        callp   .S2     copy16, b3          ; A = F
        mvkl    .S1     BUF_S, a4
        mvkh    .S1     BUF_S, a4
        mvkl    .S1     BUF_F, a5
        mvkh    .S1     BUF_F, a5
        mvkl    .S1     GAINS, a7
        mvkh    .S1     GAINS, a7
        ldw     .D1T1   *+a7(8), a6         ; SendB x RouteB
        nop     4
        callp   .S2     scale16, b3
        mvk     .L1     BUS_B, a11
        b       .S1     run_bus
        addkpc  .S2     e_mix, b10, 4
e_mix:
        mvkl    .S1     BUF_A, a4
        mvkh    .S1     BUF_A, a4
        mvkl    .S1     BUF_F, a5
        mvkh    .S1     BUF_F, a5
        mvkl    .S1     GAINS, a7
        mvkh    .S1     GAINS, a7
        ldw     .D1T1   *+a7(12), a6        ; cA
        ldw     .D1T2   *+a7(16), b6        ; cB
        nop     4
        callp   .S2     mix16, b3           ; F = cA x A + cB x F
        mvk     .L1     POST, a11
        b       .S1     run_bus
        addkpc  .S2     e_master, b10, 4
serial:
        mvk     .L1     PRE, a11
        b       .S1     run_bus
        addkpc  .S2     e_master, b10, 4
e_master:
        mvk     .L1     S_MASTER, a4        ; the chain's end, both modes: Master
        callp   .S2     pct, b3
        mvkl    .S1     MASTER, a5
        mvkh    .S1     MASTER, a5
        callp   .S2     smooth, b3
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mv      .L1     a4, a5
        callp   .S2     scale16, b3         ; A6 = the smoothed Master
        callp   .S2     limit, b3           ; then the safety limiter
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mv      .L1     a4, a5
        callp   .S2     scale16, b3         ; A6 = its gain
e_out:
        callp   .S2     latch, b3
        mvk     .L2     6, b0
        stw     .D2T2   b0, *+b14(SLOT_VAR) ; as the stock loop leaves it
        mvkl    .S2     AFTER_LOOP, b0
        mvkh    .S2     AFTER_LOOP, b0
        b       .S2     b0
        nop     5

; Every slot whose bus (LAYOUT & B13) is A11, in slot order, the way the stock
; loop calls it (B14+576 = slot, A4 = slot state, call 0xC00EE930[slot]).
; Returns to B10.
run_bus:
        mvk     .L1     0, a12
rb_slot:
        mvkl    .S1     LAYOUT, a0
        mvkh    .S1     LAYOUT, a0
        ldbu    .D1T1   *+a0[a12], a0
        nop     4
        and     .L1X    a0, b13, a0
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

; MAIL -> LAYOUT where the routing probe ran (0x80 | bus); other slots keep
; their saved bus. Then clear MAIL. Uses A0-A5.
latch:
        mvkl    .S1     MAIL, a4
        mvkh    .S1     MAIL, a4
        mvkl    .S1     LAYOUT, a5
        mvkh    .S1     LAYOUT, a5
        mvk     .L1     6, a1
        mvk     .L1     0, a3
lt_slot:
        ldbu    .D1T1   *a4, a2
        nop     4
        extu    .S1     a2, 24, 31, a0      ; bit 7: the probe ran
        and     .L1     3, a2, a2
  [a0]  stb     .D1T1   a2, *a5
        add     .L1     1, a5, a5
        stb     .D1T1   a3, *a4++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     lt_slot
        nop     5
        b       .S2     b3
        nop     5

; Targets from the settings, smoothed into GAINS. Uses A0-A9, A13-A15, B3,
; B11 (return).
gains_update:
        mv      .L2     b3, b11
        mvk     .L1     S_SEND, a4
        callp   .S2     pct, b3
        callp   .S2     law, b3
        mv      .L1     a4, a13             ; SendA
        mv      .L1     a5, a14             ; SendB
        mvk     .L1     S_RA, a4
        callp   .S2     pct, b3
        mpysp   .M1     a4, a13, a4
        nop     3
        mvkl    .S1     GAINS + 4, a5
        mvkh    .S1     GAINS + 4, a5
        callp   .S2     smooth, b3
        mvk     .L1     S_RB, a4
        callp   .S2     pct, b3
        mpysp   .M1     a4, a14, a4
        nop     3
        mvkl    .S1     GAINS + 8, a5
        mvkh    .S1     GAINS + 8, a5
        callp   .S2     smooth, b3
        ; crossfade: DJ unless the curve says otherwise
        mvk     .L1     S_XF, a4
        callp   .S2     pct, b3
        mv      .L1     a4, a15             ; x
        callp   .S2     law, b3
        mv      .L1     a4, a13             ; xA
        mv      .L1     a5, a14             ; xB
        mvkl    .S1     LIVE, a0
        mvkh    .S1     LIVE, a0
        ldbu    .D1T1   *+a0(S_CURVE), a2
        ldbu    .D1T1   *+a0(S_XF), a3
        nop     4
        cmpeq   .L1     2, a2, a1
  [!a1] b       .S1     gu_smooth
        nop     5
        ; Cut: both full, a bus drops only at its far end
        mvkl    .S1     F_ONE, a13
        mvkh    .S1     F_ONE, a13
        mv      .L1     a13, a14
        mvk     .S1     100, a0
        cmpeq   .L1     a3, a0, a1
  [a1]  mvk     .L1     0, a13
        cmpeq   .L1     0, a3, a1
  [a1]  mvk     .L1     0, a14
        b       .S1     gu_mix
        nop     5
gu_smooth:
        cmpeq   .L1     0, a2, a1
  [!a1] b       .S1     gu_mix
        nop     5
        ; Smooth: equal power, xA = f(1 - x), xB = f(x)
        mv      .L1     a15, a4
        callp   .S2     eqp, b3
        mv      .L1     a4, a14
        mvkl    .S1     F_ONE, a0
        mvkh    .S1     F_ONE, a0
        subsp   .L1     a0, a15, a4
        nop     3
        callp   .S2     eqp, b3
        mv      .L1     a4, a13
gu_mix:
        mvk     .L1     S_MA, a4
        callp   .S2     pct, b3
        mpysp   .M1     a4, a13, a4
        nop     3
        mvkl    .S1     GAINS + 12, a5
        mvkh    .S1     GAINS + 12, a5
        callp   .S2     smooth, b3
        mvk     .L1     S_MB, a4
        callp   .S2     pct, b3
        mpysp   .M1     a4, a14, a4
        nop     3
        mvkl    .S1     LIVE, a0
        mvkh    .S1     LIVE, a0
        ldbu    .D1T1   *+a0(S_PHASE), a1
        mvk     .L1     0, a0
        mvkh    .S1     0x80000000, a0
        nop     3
  [a1]  xor     .L1     a4, a0, a4          ; Phase Invert B: flip the sign
        mvkl    .S1     GAINS + 16, a5
        mvkh    .S1     GAINS + 16, a5
        callp   .S2     smooth, b3
        b       .S2     b11
        nop     5

; A4 = setting A4 x 0.01 (float). Uses A0.
pct:
        mvkl    .S1     LIVE, a0
        mvkh    .S1     LIVE, a0
        ldbu    .D1T1   *+a0[a4], a4
        nop     4
        intsp   .L1     a4, a4
        nop     3
        mvkl    .S1     F_001, a0
        mvkh    .S1     F_001, a0
        mpysp   .M1     a4, a0, a4
        nop     3
        b       .S2     b3
        nop     5

; x in A4 (0-1) -> A4 = min(1, 2 - 2x), A5 = min(1, 2x): both full at the
; centre (Send, DJ crossfade). Uses A0, A1.
law:
        addsp   .L1     a4, a4, a5
        nop     3
        mvkl    .S1     F_TWO, a0
        mvkh    .S1     F_TWO, a0
        subsp   .L1     a0, a5, a4
        nop     3
        mvkl    .S1     F_ONE, a0
        mvkh    .S1     F_ONE, a0
        cmpgtsp .S1     a4, a0, a1
        nop     1
  [a1]  mv      .L1     a0, a4
        cmpgtsp .S1     a5, a0, a1
        nop     1
  [a1]  mv      .L1     a0, a5
        b       .S2     b3
        nop     5

; A4 = t (1.5 - 0.5 t^2), about sin(pi t / 2) (equal power, -0.25 dB at the
; centre). Uses A0, A5.
eqp:
        mpysp   .M1     a4, a4, a5
        nop     3
        mvkl    .S1     F_HALF, a0
        mvkh    .S1     F_HALF, a0
        mpysp   .M1     a5, a0, a5
        nop     3
        mvkl    .S1     F_ONE5, a0
        mvkh    .S1     F_ONE5, a0
        subsp   .L1     a0, a5, a5
        nop     3
        mpysp   .M1     a4, a5, a4
        nop     3
        b       .S2     b3
        nop     5

; *A5 += (A4 - *A5) / 4. Uses A0, A4, A6.
smooth:
        ldw     .D1T1   *a5, a6
        nop     4
        subsp   .L1     a4, a6, a4
        nop     3
        mvkl    .S1     F_QUARTER, a0
        mvkh    .S1     F_QUARTER, a0
        mpysp   .M1     a4, a0, a4
        nop     3
        addsp   .L1     a6, a4, a6
        nop     3
        stw     .D1T1   a6, *a5
        b       .S2     b3
        nop     5

; Safety limiter on F: the gain drops at once so the block peak stays at
; 0.98, then climbs back by 0.001 per block (1 -> 0.5 -> 1 in about 90 ms).
; ponytail: block-rate peak, no lookahead: a jump inside one block is cut a
; block late (out_to_int still clips at +-1.0). Uses A0-A9. Sets GAINS+20.
limit:
        mvkl    .S1     BUF_F, a4
        mvkh    .S1     BUF_F, a4
        mvk     .S1     16, a1
        mvk     .L1     0, a7               ; peak
lm_peak:
        ldw     .D1T1   *a4++, a2
        nop     4
        abssp   .S1     a2, a2
        nop     1
        cmpgtsp .S1     a2, a7, a0
        nop     1
  [a0]  mv      .L1     a2, a7
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     lm_peak
        nop     5
        mvkl    .S1     GAINS, a5
        mvkh    .S1     GAINS, a5
        ldw     .D1T1   *+a5(20), a6        ; limiter gain
        nop     4
        mpysp   .M1     a7, a6, a8
        nop     3
        mvkl    .S1     F_CEIL, a9
        mvkh    .S1     F_CEIL, a9
        cmpgtsp .S1     a8, a9, a0
        nop     1
  [!a0] b       .S1     lm_release
        nop     5
        rcpsp   .S1     a7, a2              ; 1 / peak, one Newton step
        nop     1
        mpysp   .M1     a7, a2, a3
        nop     3
        mvkl    .S1     F_TWO, a0
        mvkh    .S1     F_TWO, a0
        subsp   .L1     a0, a3, a3
        nop     3
        mpysp   .M1     a2, a3, a2
        nop     3
        mpysp   .M1     a2, a9, a6          ; 0.98 / peak
        mvkl    .S1     LIMHIT, a0
        mvkh    .S1     LIMHIT, a0
        mvk     .L1     1, a1
        stb     .D1T1   a1, *a0
        b       .S1     lm_store
        nop     5
lm_release:
        mvkl    .S1     F_REL, a0
        mvkh    .S1     F_REL, a0
        addsp   .L1     a6, a0, a6
        nop     3
        mvkl    .S1     F_ONE, a0
        mvkh    .S1     F_ONE, a0
        cmpgtsp .S1     a6, a0, a1
        nop     1
  [a1]  mv      .L1     a0, a6
lm_store:
        stw     .D1T1   a6, *+a5(20)
        b       .S2     b3
        nop     5

; 16 floats from A4 x A6 to A5 (may be the same buffer). Uses A1, A2.
scale16:
        mvk     .S1     16, a1
sc_loop:
        ldw     .D1T1   *a4++, a2
        nop     4
        mpysp   .M1     a2, a6, a2
        nop     3
        stw     .D1T1   a2, *a5++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     sc_loop
        nop     5
        b       .S2     b3
        nop     5

; A5[i] = A6 x A4[i] + B6 x A5[i], 16 floats. Uses A1-A3.
mix16:
        mvk     .S1     16, a1
mx_loop:
        ldw     .D1T1   *a4++, a2
        ldw     .D1T1   *a5, a3
        nop     4
        mpysp   .M1     a2, a6, a2
        mpysp   .M1X    a3, b6, a3
        nop     3
        addsp   .L1     a2, a3, a2
        nop     3
        stw     .D1T1   a2, *a5++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     mx_loop
        nop     5
        b       .S2     b3
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

; ---------------------------------------------------------------- saving

; Patch load into the live patch (A4 = 0xC009BF58) or into its saved copy
; (A4 = 0xC009C07C); B4 = packed record. B3 = return into the OS.
; unpack_live runs in the load routine (0xC00B88E4): A11 = the patch it leaves
; (-1: none), B11 = 1 when its stock IS_DIRTY (0xC00B892C, not hookable) found
; edits, the live patch already copied to its B15+4 for the save at 0xC00B89F4.
; Mixer-only edits get that same copy and save, like any stock edit.
unpack_live:
        mvk     .L1     -1, a0
        cmpeq   .L1     a11, a0, a1
  [!a1] mv      .L1X    b11, a1
  [a1]  b       .S1     ul_go               ; no patch left, or stock saves it
        nop     5
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        stw     .D2T1   a4, *+b15(8)
        stw     .D2T2   b4, *+b15(12)
        callp   .S2     dirty, b3           ; here only the settings or buses can differ
        mv      .L1     a4, a1
  [!a1] b       .S1     ul_pop
        nop     5
        mv      .L1X    b15, a4
        addk    .S1     20, a4              ; the load routine's B15+4
        mvkl    .S2     LIVE_PATCH, b4
        mvkh    .S2     LIVE_PATCH, b4
        mvk     .S1     0x124, a6
        mvkl    .S2     MEMCPY, b5
        mvkh    .S2     MEMCPY, b5
        b       .S2     b5
        addkpc  .S2     ul_set, b3, 4
ul_set:
        mvk     .L2     1, b11
ul_pop:
        ldw     .D2T2   *+b15(4), b3
        ldw     .D2T1   *+b15(8), a4
        ldw     .D2T2   *+b15(12), b4
        nop     4
        addk    .S2     16, b15
ul_go:
        mvk     .L1     0, a0
        b       .S1     unpack_hook
        nop     5
unpack_saved:
        mvk     .L1     1, a0
unpack_hook:
        addk    .S2     -24, b15
        stw     .D2T2   b3, *+b15(4)
        stw     .D2T1   a10, *+b15(8)
        stw     .D2T1   a11, *+b15(12)
        stw     .D2T1   a12, *+b15(16)
        mv      .L1     a4, a10             ; RAM patch
        mv      .L1X    b4, a11             ; packed
        mv      .L1     a0, a12             ; 1 = saved copy
        mvkl    .S2     UNPACK_WRAP, b5
        mvkh    .S2     UNPACK_WRAP, b5
        b       .S2     b5
        addkpc  .S2     uh_bytes, b3, 4
uh_bytes:
        mv      .L2     b11, b1             ; the load routine's B11: it will auto
        mv      .L1     a12, a1             ; save the patch it leaves after this
  [a1]  mvk     .L2     0, b1
  [!b1] b       .S1     uh_get
        nop     5
        mvkl    .S1     LIVE, a4            ; that save gets the settings it had
        mvkh    .S1     LIVE, a4
        mvkl    .S2     PREV, b4
        mvkh    .S2     PREV, b4
        callp   .S2     copy18, b3
        mvkl    .S1     PEND, a0
        mvkh    .S1     PEND, a0
        mvk     .L1     1, a1
        stb     .D1T1   a1, *a0
uh_get:
        mv      .L1     a11, a4
        mvkl    .S2     SAVED, b4
        mvkh    .S2     SAVED, b4
        mvkl    .S2     LIVE, b5
        mvkh    .S2     LIVE, b5
        mv      .L1     a12, a1
  [!a1] mv      .L2     b5, b4
        callp   .S2     get_bytes, b3
        mv      .L1     a12, a1
  [a1]  b       .S1     uh_mask
        nop     5
        mvkl    .S1     LIVE, a4            ; a loaded patch is as saved
        mvkh    .S1     LIVE, a4
        mvkl    .S2     SAVED, b4
        mvkh    .S2     SAVED, b4
        callp   .S2     copy18, b3
uh_mask:
        mv      .L1     a10, a4
        callp   .S2     mask_p8, b3
        ldw     .D2T2   *+b15(4), b3
        ldw     .D2T1   *+b15(8), a10
        ldw     .D2T1   *+b15(12), a11
        ldw     .D2T1   *+b15(16), a12
        nop     4
        addk    .S2     24, b15
        b       .S2     b3
        nop     5

; The patch sent to an editor: A4 = packed (0xC009C2A8), B4 = live patch.
pack_dump:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        stw     .D2T1   a10, *+b15(8)
        mv      .L1     a4, a10
        mvkl    .S2     PACK_WRAP, b5
        mvkh    .S2     PACK_WRAP, b5
        b       .S2     b5
        addkpc  .S2     pd_bytes, b3, 4
pd_bytes:
        mv      .L1     a10, a4
        mvkl    .S2     LIVE, b4
        mvkh    .S2     LIVE, b4
        callp   .S2     put_bytes, b3
        ldw     .D2T2   *+b15(4), b3
        ldw     .D2T1   *+b15(8), a10
        nop     4
        addk    .S2     16, b15
        b       .S2     b3
        nop     5

; Every patch record save: A4 = record, B4 = packed record, B3 = return into
; the OS (the stock 0xC00B84C0, which this replaces, returns 0).
rec_save:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        stw     .D2T1   a4, *+b15(8)
        stw     .D2T2   b4, *+b15(12)
        mvkl    .S2     SAVE_BUF, b0
        mvkh    .S2     SAVE_BUF, b0
        cmpeq   .L2     b4, b0, b0
  [!b0] b       .S1     rs_stock            ; a packed copy: its own bytes
        nop     5
        mv      .L1X    b4, a4
        mvkl    .S1     PEND, a6
        mvkh    .S1     PEND, a6
        ldbu    .D1T2   *a6, b1             ; 1: a patch load saving the patch it left
        mvk     .L1     0, a7
        stb     .D1T1   a7, *a6
        mvkl    .S2     LIVE, b4
        mvkh    .S2     LIVE, b4
        nop     1
  [b1]  mvkl    .S2     PREV, b4
  [b1]  mvkh    .S2     PREV, b4
        callp   .S2     put_bytes, b3
  [b1]  b       .S1     rs_stock            ; SAVED already holds the new patch's
        nop     5
        mvkl    .S1     LIVE, a4
        mvkh    .S1     LIVE, a4
        mvkl    .S2     SAVED, b4
        mvkh    .S2     SAVED, b4
        callp   .S2     copy18, b3          ; saved = live
rs_stock:
        ldw     .D2T1   *+b15(8), a4
        ldw     .D2T2   *+b15(12), b4
        nop     4
        mvkl    .S2     REC_SAVE, b5
        mvkh    .S2     REC_SAVE, b5
        b       .S2     b5
        addkpc  .S2     rs_done, b3, 4
rs_done:
        ldw     .D2T2   *+b15(4), b3
        nop     4
        addk    .S2     16, b15
        mvk     .L1     0, a4
        b       .S2     b3
        nop     5

; IS_DIRTY, or the settings or buses differ from the saved ones. B3 = return.
dirty:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        mvkl    .S2     IS_DIRTY, b5
        mvkh    .S2     IS_DIRTY, b5
        b       .S2     b5
        addkpc  .S2     dt_cmp, b3, 4
dt_cmp:
        ldw     .D2T2   *+b15(4), b3
        mvkl    .S1     LIVE, a5
        mvkh    .S1     LIVE, a5
        mvkl    .S1     SAVED, a6
        mvkh    .S1     SAVED, a6
        mvk     .S1     18, a1
dt_loop:
        ldbu    .D1T1   *a5++, a2
        ldbu    .D1T1   *a6++, a3
        nop     4
        cmpeq   .L1     a2, a3, a0
  [!a0] mvk     .L1     1, a4
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     dt_loop
        nop     5
        addk    .S2     16, b15
        b       .S2     b3
        nop     5

; Bytes 14, 15 of the six packed slot blocks (A4) -> 12 bytes at B4, byte 17
; (bits 0-1) -> the 6 buses after them; without MAGIC the defaults (every bus
; PRE). Uses A0-A6.
get_bytes:
        mv      .L1X    b4, a5
        add     .L1X    12, b4, a6
        addk    .S1     14, a4
        mvk     .L1     6, a1
gb_loop:
        ldbu    .D1T1   *a4, a2
        ldbu    .D1T1   *+a4(1), a3
        ldbu    .D1T1   *+a4(3), a0
        nop     4
        stb     .D1T1   a2, *a5++
        stb     .D1T1   a3, *a5++
        and     .L1     3, a0, a0
        stb     .D1T1   a0, *a6++
        addk    .S1     18, a4
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     gb_loop
        nop     5
        ldbu    .D1T1   *-a5(1), a2
        nop     4
        mvk     .S1     MAGIC, a0
        cmpeq   .L1     a2, a0, a1
  [a1]  b       .S2     b3
        nop     5
        mvkl    .S1     DEFAULTS, a4        ; no settings in this patch
        mvkh    .S1     DEFAULTS, a4
        sub     .L1     a5, 12, a5
        b       .S1     copy18a
        nop     5

; 12 bytes at B4 -> bytes 14, 15 of the six packed slot blocks (A4), the 6
; buses after them -> byte 17. Uses A1-A6.
put_bytes:
        mv      .L1X    b4, a5
        add     .L1X    12, b4, a6
        addk    .S1     14, a4
        mvk     .L1     6, a1
pb_loop:
        ldbu    .D1T1   *a5++, a2
        ldbu    .D1T1   *a5++, a3
        nop     4
        stb     .D1T1   a2, *a4
        stb     .D1T1   a3, *+a4(1)
        ldbu    .D1T1   *a6++, a2
        nop     4
        stb     .D1T1   a2, *+a4(3)
        addk    .S1     18, a4
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     pb_loop
        nop     5
        b       .S2     b3
        nop     5

; 18 bytes (12 + 6 buses) from A4 to B4 (copy18) or A5 (copy18a). Uses A1, A2,
; A5.
copy18:
        mv      .L1X    b4, a5
copy18a:
        mvk     .S1     18, a1
c18_loop:
        ldbu    .D1T1   *a4++, a2
        nop     4
        stb     .D1T1   a2, *a5++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     c18_loop
        nop     5
        b       .S2     b3
        nop     5

; P8 (word 9 of each 44-byte slot of the RAM patch at A4) back to 12 bits:
; the stock unpack read the setting bytes into its top bits. Uses A1, A2.
mask_p8:
        addk    .S1     36, a4
        mvk     .L1     6, a1
mp_loop:
        ldw     .D1T1   *a4, a2
        nop     4
        extu    .S1     a2, 20, 20, a2
        stw     .D1T1   a2, *a4
        addk    .S1     44, a4
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     mp_loop
        nop     5
        b       .S2     b3
        nop     5

; ---------------------------------------------------------------- bus follows the effect

; Each wraps a stock function at its only call site (arguments in A4 / B4,
; B3 = return, all three untouched): it moves LAYOUT as stock is about to
; move the effects, then jumps to stock. Before stock, not after: stock
; mutes the slots within microseconds of its start (fade, then the slot
; mutes), while after it come the slow parts with the slots playing again
; (the swap's delay memory copy, the add / delete type change). Edited mark:
; stock's own (the records move), and LAYOUT now differs from SAVED's buses.
; Uses A0-A8, B5-B8.

; Effect Chain move (0xC00B76A4, lifted effect turned): the effects at rows
; A4 and B4 trade places (slot = count - 1 - row, 0xC00B6BAC). Both bytes in
; one execute packet: the audio never runs half a swap.
mv_swap:
        mvkl    .S1     COUNT, a0
        mvkh    .S1     COUNT, a0
        ldw     .D1T1   *a0, a0
        nop     4
        sub     .L1     a0, 1, a0
        sub     .L1     a0, a4, a5          ; slot A
        sub     .L1X    a0, b4, a6          ; slot B
        cmpgtu  .L1     6, a5, a1
        cmpgtu  .L1     6, a6, a2
        and     .L1     a1, a2, a1
  [!a1] b       .S1     ms_stock
        nop     5
        mvkl    .S1     LAYOUT, a3
        mvkh    .S1     LAYOUT, a3
        ldbu    .D1T1   *+a3[a5], a7
        ldbu    .D1T1   *+a3[a6], a8
        mv      .L2X    a3, b6
        mv      .L2X    a6, b7
        nop     2
        mv      .L2X    a7, b8
        stb     .D1T1   a8, *+a3[a5]
||      stb     .D2T2   b8, *+b6[b7]
ms_stock:
        mvkl    .S2     FX_SWAP, b5
        mvkh    .S2     FX_SWAP, b5
        b       .S2     b5
        nop     5

; Effect add (0xC00A7BE0, screen 33 ENTER, A4 = effect id): stock inserts at
; slot ANCHOR + SIDE and moves the slots from there up one (the last is
; always empty: add needs fewer than six). The new effect gets the anchor's
; bus.
mv_add:
        ldw     .D2T1   *+b14(ANCHOR), a5
        ldw     .D2T1   *+b14(SIDE), a6
        nop     4
        add     .L1     a5, a6, a6          ; the new effect's slot
        cmpgtu  .L1     6, a5, a1
        cmpgtu  .L1     6, a6, a2
        and     .L1     a1, a2, a1
  [!a1] b       .S1     ma_stock
        nop     5
        mvkl    .S1     LAYOUT, a3
        mvkh    .S1     LAYOUT, a3
        ldbu    .D1T1   *+a3[a5], a7        ; the anchor's bus
        add     .L1     5, a3, a8           ; from the last slot down
        mvk     .L1     5, a0
        sub     .L1     a0, a6, a1          ; slots to move up
ma_loop:
  [!a1] b       .S1     ma_new
        nop     5
        ldbu    .D1T1   *-a8(1), a0
        nop     4
        stb     .D1T1   a0, *a8--
        sub     .L1     a1, 1, a1
        b       .S1     ma_loop
        nop     5
ma_new:
        stb     .D1T1   a7, *+a3[a6]
ma_stock:
        mvkl    .S2     FX_ADD, b5
        mvkh    .S2     FX_ADD, b5
        b       .S2     b5
        nop     5

; Effect delete (0xC00A8294, screen 2 YES): stock deletes the slot under the
; cursor (its own lookup at 0xC00C2098: CURSOR_SLOTS[6 x VIEW + CURSOR]) and
; moves the slots above it down one; the last slot gets PRE. With one effect
; stock only empties it (the shift moves the empty slots' buses, PRE unless
; set on the BUS pages).
mv_delete:
        mvkl    .S1     VIEW, a0
        mvkh    .S1     VIEW, a0
        ldw     .D1T1   *a0, a0
        mvkl    .S1     CURSOR, a1
        mvkh    .S1     CURSOR, a1
        ldb     .D1T1   *a1, a1
        nop     4
        mvk     .S1     6, a2
        mpy     .M1     a0, a2, a0
        nop     1
        add     .L1     a0, a1, a0
        mvkl    .S1     CURSOR_SLOTS, a2
        mvkh    .S1     CURSOR_SLOTS, a2
        ldw     .D1T1   *+a2[a0], a5        ; the slot deleted
        nop     4
        cmpgtu  .L1     6, a5, a1
  [!a1] b       .S1     md_stock
        nop     5
        mvkl    .S1     LAYOUT, a3
        mvkh    .S1     LAYOUT, a3
        add     .L1     a3, a5, a8
        mvk     .L1     5, a0
        sub     .L1     a0, a5, a1          ; slots to move down
md_loop:
  [!a1] b       .S1     md_last
        nop     5
        ldbu    .D1T1   *+a8(1), a0
        nop     4
        stb     .D1T1   a0, *a8++
        sub     .L1     a1, 1, a1
        b       .S1     md_loop
        nop     5
md_last:
        mvk     .L1     PRE, a0
        stb     .D1T1   a0, *+a3(5)
md_stock:
        mvkl    .S2     FX_DELETE, b5
        mvkh    .S2     FX_DELETE, b5
        b       .S2     b5
        nop     5

; ---------------------------------------------------------------- MIXER screen

; Screen 15 keys (switch-table entry: the event pair is in the dispatcher's
; frame). Knob 1-3 turn: the setting under it; knob 1 press: next page;
; knob 2 (EXIT): back to the menu.
keys_e:
        lddw    .D2T1   *+b15(8), a5:a4
        mvkl    .S2     KEY_DONE, b3
        mvkh    .S2     KEY_DONE, b3
        b       .S1     keys
        nop     5
keys:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        mvk     .S1     EV_TURN, a0
        sub     .L1     a4, a0, a6          ; knob 0-2
        cmpgtu  .L1     3, a6, a1
  [a1]  b       .S1     k_turn
        nop     5
        mvk     .S1     EV_ENTER, a0
        cmpeq   .L1     a4, a0, a1
  [a1]  b       .S1     k_page
        nop     5
        mvk     .S1     EV_EXIT, a0
        cmpeq   .L1     a4, a0, a1
  [!a1] b       .S1     k_none
        nop     5
        mvk     .L1     0, a4               ; the menu
        mvk     .L2     3, b4
        mvkl    .S2     SET_SCREEN, b5
        mvkh    .S2     SET_SCREEN, b5
        b       .S2     b5
        addkpc  .S2     k_redraw, b3, 4
k_redraw:
        mvk     .L1     1, a4
        b       .S1     k_ret
        nop     5
k_none:
        mvk     .L1     0, a4
k_ret:
        ldw     .D2T2   *+b15(4), b3
        nop     4
        addk    .S2     16, b15
        b       .S2     b3
        nop     5
k_page:
        mvkl    .S1     PAGE, a0
        mvkh    .S1     PAGE, a0
        ldw     .D1T1   *a0, a2
        nop     4
        add     .L1     1, a2, a2
        cmpgt   .L1     8, a2, a1
  [!a1] mvk     .L1     0, a2
        stw     .D1T1   a2, *a0
        b       .S1     k_redraw
        nop     5
k_turn:
        mvkl    .S1     PAGE, a0
        mvkh    .S1     PAGE, a0
        ldw     .D1T1   *a0, a2
        nop     4
        shl     .S1     a2, 2, a2
        add     .L1     a2, a6, a2
        mvkl    .S1     PAGES, a0
        mvkh    .S1     PAGES, a0
        ldbu    .D1T1   *+a0[a2], a2        ; setting
        nop     4
        mvk     .S1     S_LAST, a0
        cmpgtu  .L1     a2, a0, a1
  [a1]  b       .S1     k_none              ; no setting under this knob
        nop     5
        mvkl    .S1     MAXES, a7
        mvkh    .S1     MAXES, a7
        ldbu    .D1T1   *+a7[a2], a7
        mvkl    .S1     LIVE, a0
        mvkh    .S1     LIVE, a0
        ldbu    .D1T1   *+a0[a2], a3
        nop     4
        add     .L1     a3, a5, a3          ; + steps
        cmpgt   .L1     0, a3, a1
  [a1]  mvk     .L1     0, a3
        cmpgt   .L1     a3, a7, a1
  [a1]  mv      .L1     a7, a3
        stb     .D1T1   a3, *+a0[a2]
        mvkl    .S2     UI_REFRESH, b5      ; the edited mark, then the auto save timer
        mvkh    .S2     UI_REFRESH, b5
        b       .S2     b5
        addkpc  .S2     kt_post, b3, 4
kt_post:
        ldw     .D2T1   *+b14(UI_EVENT_OFS), a4
        mvk     .S2     64, b4
        nop     3
        mvkl    .S2     EVENT_POST, b5
        mvkh    .S2     EVENT_POST, b5
        b       .S2     b5
        addkpc  .S2     k_redraw, b3, 4

; Screen 15 draw: page title, a row per knob (name, value), softkeys.
; Frame: +4 snprintf format, +8 its value, +28 y, +32.. saved registers.
draw_e:
        mvkl    .S2     DRAW_DONE, b3
        mvkh    .S2     DRAW_DONE, b3
        b       .S1     draw
        nop     5
draw:
        addk    .S2     -48, b15
        stw     .D2T2   b3, *+b15(32)
        stw     .D2T1   a10, *+b15(36)
        stw     .D2T1   a11, *+b15(40)
        stw     .D2T1   a12, *+b15(44)
        mvkl    .S1     PAGE, a0
        mvkh    .S1     PAGE, a0
        ldw     .D1T1   *a0, a10            ; page
        nop     4
        mvkl    .S1     titles, a0
        mvkh    .S1     titles, a0
        ldw     .D1T1   *+a0[a10], a4
        nop     4
        mvkl    .S2     DRAW_TITLE, b5
        mvkh    .S2     DRAW_TITLE, b5
        b       .S2     b5
        addkpc  .S2     d_rows, b3, 4
d_rows:
        mvk     .L1     0, a11              ; row = knob
d_row:
        shl     .S1     a10, 2, a0
        add     .L1     a0, a11, a0
        mvkl    .S1     PAGES, a1
        mvkh    .S1     PAGES, a1
        ldbu    .D1T1   *+a1[a0], a12       ; setting
        nop     4
        mvk     .S1     S_LAST, a0
        cmpgtu  .L1     a12, a0, a1
  [a1]  b       .S1     d_next
        nop     5
        mvk     .S1     10, a0
        mpy     .M1     a11, a0, a0
        nop     1
        addk    .S1     12, a0              ; y = 12 + 10 x row
        stw     .D2T1   a0, *+b15(28)
        mv      .L2X    a0, b6
        mvkl    .S1     names, a0
        mvkh    .S1     names, a0
        ldw     .D1T2   *+a0[a12], b4
        mvk     .L1     0, a4
        mvk     .L1     1, a6               ; x
        nop     2
        mvkl    .S2     DRAW_TEXT, b5
        mvkh    .S2     DRAW_TEXT, b5
        b       .S2     b5
        addkpc  .S2     d_value, b3, 4
d_value:
        mvkl    .S1     enums, a0
        mvkh    .S1     enums, a0
        ldw     .D1T1   *+a0[a12], a0       ; value names, or 0: a number
        mvkl    .S1     LIVE, a1
        mvkh    .S1     LIVE, a1
        ldbu    .D1T1   *+a1[a12], a1
        nop     4
  [!a0] b       .S1     d_num
        nop     5
        ldw     .D1T2   *+a0[a1], b4
        nop     4
        b       .S1     d_text
        nop     5
d_num:
        stw     .D2T1   a1, *+b15(8)
        mvkl    .S1     fmt_d, a0
        mvkh    .S1     fmt_d, a0
        stw     .D2T1   a0, *+b15(4)
        mvkl    .S1     numbuf, a4
        mvkh    .S1     numbuf, a4
        mvk     .L2     8, b4
        mvkl    .S2     SNPRINTF, b5
        mvkh    .S2     SNPRINTF, b5
        b       .S2     b5
        addkpc  .S2     d_numdone, b3, 4
d_numdone:
        mvkl    .S2     numbuf, b4
        mvkh    .S2     numbuf, b4
d_text:
        ldw     .D2T2   *+b15(28), b6       ; y
        mvk     .L1     0, a4
        mvk     .S1     78, a6              ; x
        nop     2
        mvkl    .S2     DRAW_TEXT, b5
        mvkh    .S2     DRAW_TEXT, b5
        b       .S2     b5
        addkpc  .S2     d_next, b3, 4
d_next:
        add     .L1     1, a11, a11
        cmpgt   .L1     3, a11, a1
  [a1]  b       .S1     d_row
        nop     5
        mvkl    .S1     HOLD, a0            ; LIMIT on the OUT page
        mvkh    .S1     HOLD, a0
        ldw     .D1T1   *a0, a1
        nop     4
  [a1]  mvk     .L1     1, a1
        stb     .D1T1   a1, *-a0(2)         ; SHOWN
        cmpeq   .L1     5, a10, a0
        and     .L1     a0, a1, a1
  [!a1] b       .S1     d_soft
        nop     5
        mvk     .L1     0, a4
        mvkl    .S2     s_limit, b4
        mvkh    .S2     s_limit, b4
        mvk     .L1     1, a6
        mvk     .S2     32, b6
        mvkl    .S2     DRAW_TEXT, b5
        mvkh    .S2     DRAW_TEXT, b5
        b       .S2     b5
        addkpc  .S2     d_soft, b3, 4
d_soft:
        mvk     .L1     0, a4               ; softkeys: PAGE, EXIT, blank
        mvkl    .S2     s_page, b4
        mvkh    .S2     s_page, b4
        mvk     .L1     0, a6
        mvkl    .S2     SOFTKEY, b5
        mvkh    .S2     SOFTKEY, b5
        b       .S2     b5
        addkpc  .S2     d_sk1, b3, 4
d_sk1:
        mvk     .L1     1, a4
        mvkl    .S2     STR_EXIT, b4
        mvkh    .S2     STR_EXIT, b4
        mvk     .L1     0, a6
        mvkl    .S2     SOFTKEY, b5
        mvkh    .S2     SOFTKEY, b5
        b       .S2     b5
        addkpc  .S2     d_sk2, b3, 4
d_sk2:
        mvk     .L1     2, a4
        mvkl    .S2     STR_BLANK, b4
        mvkh    .S2     STR_BLANK, b4
        mvk     .L1     0, a6
        mvkl    .S2     SOFTKEY, b5
        mvkh    .S2     SOFTKEY, b5
        b       .S2     b5
        addkpc  .S2     d_done, b3, 4
d_done:
        ldw     .D2T2   *+b15(32), b3
        ldw     .D2T1   *+b15(36), a10
        ldw     .D2T1   *+b15(40), a11
        ldw     .D2T1   *+b15(44), a12
        nop     4
        addk    .S2     48, b15
        b       .S2     b3
        nop     5

; Every 16 ms round of Task_SwitchNrmlSpdRead, before midi_clock's poll (B3
; returns into the task). LIMHIT -> HOLD; a redraw when the LIMIT tag the OUT
; page shows is out of date. Uses A0-A9, B0-B9.
poll:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        mvkl    .S1     LIMHIT, a0
        mvkh    .S1     LIMHIT, a0
        ldbu    .D1T1   *a0, a1
        ldbu    .D1T1   *+a0(1), a6         ; SHOWN
        mvkl    .S1     HOLD, a5
        mvkh    .S1     HOLD, a5
        ldw     .D1T1   *a5, a2
        mvk     .L1     0, a4
        stb     .D1T1   a4, *a0
        nop     2
  [a2]  sub     .L1     a2, 1, a2
  [a1]  mvk     .S1     HOLD_POLLS, a2
        stw     .D1T1   a2, *a5
  [a2]  mvk     .L1     1, a2
        cmpeq   .L1     a2, a6, a1
  [a1]  b       .S1     pl_out              ; the tag is up to date
        nop     5
        ldw     .D2T2   *+b14(MODE), b0
        ldw     .D2T2   *+b14(SCREEN), b1
        mvkl    .S1     PAGE, a0
        mvkh    .S1     PAGE, a0
        ldw     .D1T1   *a0, a0
        nop     4
        cmpeq   .L2     11, b0, b0
        cmpeq   .L2     15, b1, b1
        and     .L2     b0, b1, b0
        cmpeq   .L1     5, a0, a0
        and     .L2X    b0, a0, b0
  [!b0] b       .S1     pl_out              ; the OUT page is not open
        nop     5
        ldw     .D2T1   *+b14(UI_EVENT_OFS), a4
        mvk     .S2     64, b4
        nop     3
        mvkl    .S2     EVENT_POST, b5
        mvkh    .S2     EVENT_POST, b5
        b       .S2     b5
        addkpc  .S2     pl_out, b3, 4
pl_out:
        ldw     .D2T2   *+b15(4), b3
        nop     4
        addk    .S2     16, b15
        mvkl    .S2     POLL, b0
        mvkh    .S2     POLL, b0
        b       .S2     b0
        nop     5

; ---------------------------------------------------------------- MIDI CC

; CC 85-95 -> a setting (0-127 scaled to its range), else on to step.S.
; Arguments as midi_channel_msg: A6 = CC number, B6 = value, B3 = return.
cc:
        mvk     .S1     CC_FIRST, a0
        sub     .L1     a6, a0, a1
        mvk     .S1     10, a0
        cmpgtu  .L1     a1, a0, a2
  [!a2] b       .S1     cc_ours
        nop     5
        mvkl    .S2     STEP, b0            ; tail call, arguments untouched
        mvkh    .S2     STEP, b0
        b       .S2     b0
        nop     5
cc_ours:
        mvkl    .S1     cc_map, a0
        mvkh    .S1     cc_map, a0
        ldbu    .D1T1   *+a0[a1], a2        ; setting
        nop     4
        mvkl    .S1     MAXES, a0
        mvkh    .S1     MAXES, a0
        ldbu    .D1T1   *+a0[a2], a3
        nop     4
        mv      .L1X    b6, a5
        mpy     .M1     a5, a3, a5          ; value x max
        nop     1
        addk    .S1     63, a5
        mvk     .S1     259, a0
        mpy     .M1     a5, a0, a5
        nop     1
        shru    .S1     a5, 15, a5          ; (value x max + 63) / 127
        cmpgt   .L1     a5, a3, a1          ; 151 at max 150: the /127 is approximate
  [a1]  mv      .L1     a3, a5
        mvkl    .S1     LIVE, a0
        mvkh    .S1     LIVE, a0
        stb     .D1T1   a5, *+a0[a2]
        addk    .S2     -16, b15            ; the auto save timer, then a redraw
        stw     .D2T2   b3, *+b15(4)
        mvkl    .S2     UI_REFRESH, b5
        mvkh    .S2     UI_REFRESH, b5
        b       .S2     b5
        addkpc  .S2     cc_post, b3, 4
cc_post:
        ldw     .D2T1   *+b14(UI_EVENT_OFS), a4
        mvk     .S2     64, b4
        nop     3
        mvkl    .S2     EVENT_POST, b5
        mvkh    .S2     EVENT_POST, b5
        b       .S2     b5
        addkpc  .S2     cc_done, b3, 4
cc_done:
        ldw     .D2T2   *+b15(4), b3
        nop     4
        addk    .S2     16, b15
        b       .S2     b3
        nop     5

; ---------------------------------------------------------------- tables

titles: .word   s_in_t, s_route1, s_route2, s_mix1, s_mix2, s_out, s_bus1, s_bus2
names:  .word   s_mode, s_send, s_in, s_bus_a, s_bus_b, s_xfade
        .word   s_master, s_curve, s_bus_a, s_bus_b, s_phase, 0
        .word   s_s1, s_s2, s_s3, s_s4, s_s5, s_s6
enums:  .word   mode_names, 0, 0, 0, 0, 0, 0, curve_names, 0, 0, phase_names, 0
        .word   bus_names, bus_names, bus_names, bus_names, bus_names, bus_names
mode_names:  .word s_serial, s_parallel
curve_names: .word s_smooth, s_dj, s_cut
phase_names: .word s_normal, s_invert
bus_names:   .word s_pre, s_a, s_b, s_post
numbuf: .word   0, 0
; CC 85 Send, 86 Crossfade, 87 Master, 88 Input Level, 89 / 90 Route A / B,
; 91 / 92 Mix A / B, 93 Mode, 94 Curve, 95 Phase Invert B
cc_map: .byte   S_SEND, S_XF, S_MASTER, S_IN, S_RA, S_RB, S_MA, S_MB
        .byte   S_MODE, S_CURVE, S_PHASE, 0
fmt_d:      .string "%d"
            .byte 0
s_mixer:    .string "MIXER"
            .byte 0
s_route1:   .string "ROUTE 1/2"
            .byte 0
s_route2:   .string "ROUTE 2/2"
            .byte 0
s_mix1:     .string "MIX 1/2"
            .byte 0
s_mix2:     .string "MIX 2/2"
            .byte 0
s_out:      .string "OUT"
            .byte 0
s_in_t:     .string "IN"
            .byte 0
s_limit:    .string "LIMIT"
            .byte 0
s_mode:     .string "MODE"
            .byte 0
s_send:     .string "SEND"
            .byte 0
s_in:       .string "INPUT LEVEL"
            .byte 0
s_bus_a:    .string "BUS A LEVEL"
            .byte 0
s_bus_b:    .string "BUS B LEVEL"
            .byte 0
s_xfade:    .string "CROSSFADE"
            .byte 0
s_master:   .string "MASTER"
            .byte 0
s_curve:    .string "CURVE"
            .byte 0
s_phase:    .string "PHASE B"
            .byte 0
s_serial:   .string "SERIAL"
            .byte 0
s_parallel: .string "PARALLEL"
            .byte 0
s_smooth:   .string "SMOOTH"
            .byte 0
s_dj:       .string "DJ"
            .byte 0
s_cut:      .string "CUT"
            .byte 0
s_normal:   .string "NORMAL"
            .byte 0
s_invert:   .string "INVERT"
            .byte 0
s_page:     .string "PAGE"
            .byte 0
s_bus1:     .string "BUS 1/2"
            .byte 0
s_bus2:     .string "BUS 2/2"
            .byte 0
s_s1:       .string "S1"
            .byte 0
s_s2:       .string "S2"
            .byte 0
s_s3:       .string "S3"
            .byte 0
s_s4:       .string "S4"
            .byte 0
s_s5:       .string "S5"
            .byte 0
s_s6:       .string "S6"
            .byte 0
s_pre:      .string "PRE"
            .byte 0
s_a:        .string "A"
            .byte 0
s_b:        .string "B"
            .byte 0
s_post:     .string "POST"
            .byte 0
            .byte 0, 0, 0, 0
