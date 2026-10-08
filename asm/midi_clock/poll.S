; Transport block upkeep (issue #24), MS-50G 3.10 OS.
;
; Task_SwitchNrmlSpdRead polls the footswitches every 16 ms and starts each
; round with Clock_getTicks (callp at 0xC00CA630). That call is retargeted to
; poll_trampoline.S, which jumps here. This does the same job (returns the
; time in A4, keeps every callee-saved register) and on the way:
;   - clears "running" when no clock came for STALE_MS, neither since the
;     last clock nor since Start (a cable pulled without a Stop);
;   - copies a new patch TEMPO (tap, TEMPO setting, patch load) into the block
;     as BPM x 100, unless the clock is live: then clock.S owns the tempo.
;     A TEMPO change while the clock is live (the clock setting it) is only
;     noted, so after the clock stops effects keep its finer tempo until
;     TEMPO changes again.

        .include "transport.inc"
        .equ    STALE_MS, 500

        .text
        .nocmp
        .global poll_hook
poll_hook:
        addk    .S2     -8, b15
        stw     .D2T2   b3, *+b15(8)
        FARCALL CLOCK_GETTICKS              ; a4 = now, returned as is
        mvkl    .S1     VARS, a0
        mvkh    .S1     VARS, a0
        mvkl    .S2     TEMPO_VALUE, b0
        mvkh    .S2     TEMPO_VALUE, b0
        mvkl    .S1     BLOCK, a1
        mvkh    .S1     BLOCK, a1
        ldw     .D1T1   *+a0(V_LAST), a2
        ldw     .D1T1   *+a0(V_STARTT), a3
        ldw     .D1T1   *+a1(B_RUN), a8
        ldw     .D1T1   *+a0(V_PSEEN), a9
        ldw     .D2T2   *b0, b1             ; b1 = patch TEMPO
        mvk     .S1     STALE_MS, a7
        nop     3
        cmpeq   .L1     0, a2, a6           ; no clock since boot
        sub     .L1     a4, a2, a2
        sub     .L1     a4, a3, a3
        cmpgtu  .L1     a2, a7, a2
        or      .L1     a6, a2, a2          ; a2 = clock silent
        cmpgtu  .L1     a3, a7, a3          ; a3 = Start is not recent
        and     .L1     a2, a3, a3
        and     .L1     a8, a3, a1          ; running, but nothing came
  [!a1] b       .S1     tempo
        nop     5
        PUB_BEGIN
        mvk     .L1     0, a3
        stw     .D1T1   a3, *+a5(B_RUN)
        PUB_END

tempo:
        cmpeq   .L1X    a9, b1, a1
  [a1]  b       .S1     out                 ; TEMPO unchanged
        nop     5
        stw     .D1T2   b1, *+a0(V_PSEEN)
  [!a2] b       .S1     out                 ; the clock owns the tempo
        nop     5
        mvk     .S2     100, b2
        mpy     .M2     b1, b2, b2          ; 40..250 fits 16 bits
        nop     1
        PUB_BEGIN
        stw     .D1T2   b2, *+a5(B_TEMPO)
        PUB_END

out:
        ldw     .D2T2   *+b15(8), b3
        addk    .S2     8, b15
        nop     4
        b       .S2     b3
        nop     5
