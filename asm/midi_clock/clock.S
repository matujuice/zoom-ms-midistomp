; MIDI clock -> patch tempo (issue #5), MS-50G 3.10 OS.
;
; Hook: Task_MIDI's byte loop ends every byte, realtime bytes included, at
; 0xC00AF0F8 ("ldw *+b14(224),b0", read index of the receive ring). That word
; becomes "callp clock_trampoline" (trampoline.S), so this code runs once per
; received byte with the byte at B14+234 and B3 = return into Task_MIDI. It
; runs the replaced load before returning. Only callee-saved A10 is live in
; Task_MIDI here, so B0-B2 are free on the fast path.
;
; Every byte other than 0xF8 (timing clock) returns at once. Start, stop and
; continue are ignored, as before.
;
; Tempo from the clock (24 ticks per quarter note):
;   - a gap of more than GAP_MS between ticks restarts the measurement;
;   - every 24th tick is a beat; from the third beat on, the time of the last
;     two beats (48 ticks) gives bpm = (120000 + span/2) / span, span clamped
;     to 480..3000 ms, so bpm stays 40..250 like tap tempo;
;   - smoothing: a value 2 or more away from the tempo last applied is
;     applied at once; a value 1 away only when the next measurement agrees;
;     a tempo changed by hand (tap, menu, patch change) is overridden on the
;     next beat.
; Applying is what tap tempo does (0xC00B9DA8): set_setting(TEMPO, bpm), whose
; change callback takes the effect semaphore and retunes the effects, then the
; same UI refresh the MIDI CC patch uses.
;
; Task_MIDI has a 2 KB stack and the tempo callback goes deep into the effect
; code, so the slow path switches to a private 4 KB stack in free L2.

        .equ    CLOCK_GETTICKS, 0xC00DF360  ; SYS/BIOS Clock_getTicks, 1 ms
        .equ    DIVU, 0xC00DCA20            ; a4 = a4 / b4 (unsigned), RTS
        .equ    SET_SETTING, 0xC00CAC64     ; (setting, value, notify)
        .equ    TEMPO_SETTING, 0xC00EE3D8   ; value ptr, min 40, max 250
        .equ    UI_REFRESH, 0xC00ACEA4
        .equ    EVENT_POST, 0xC00CC680
        .equ    UI_EVENT_OFS, 676
        .equ    VARS, 0x1181E3C0            ; 32 zero bytes, clock_vars section
        .equ    V_COUNT, 0                  ; ticks since the last beat (0..23)
        .equ    V_LAST, 4                   ; time of the last tick
        .equ    V_BEAT1, 8                  ; time of the last beat
        .equ    V_BEAT2, 12                 ; time of the beat before
        .equ    V_BEATS, 16                 ; beats seen since restart (0..2)
        .equ    V_PEND, 20                  ; tempo 1 off, waiting to be confirmed
        .equ    V_APPLIED, 24               ; tempo this code applied last
        .equ    STACK_TOP, 0x1181FFF8       ; private stack 0x1181F000-0x1181FFFF
        .equ    GAP_MS, 250
        .equ    SPAN_MIN, 480               ; 2 beats at 250 BPM
        .equ    SPAN_MAX, 3000              ; 2 beats at 40 BPM

; Far call: B5 = target, B3 = return label. Arguments must be set before.
        .macro  FARCALL target
        mvkl    .S2     \target, b5
        mvkh    .S2     \target, b5
        b       .S2     b5
        mvkl    .S2     ret\@, b3
        mvkh    .S2     ret\@, b3
        nop     3
ret\@:
        .endm

        .text
        .nocmp
        .global clock_hook
clock_hook:
        ldbu    .D2T2   *+b14(234), b0      ; the byte just taken
        mvk     .S2     0xF8, b1
        nop     3
        cmpeq   .L2     b0, b1, b2
  [b2]  b       .S2     tick
        nop     5
        ldw     .D2T2   *+b14(224), b0      ; the replaced instruction
        b       .S2     b3
        nop     5

tick:
        addk    .S2     -32, b15
        stw     .D2T2   b3, *+b15(8)
        stw     .D2T1   a10, *+b15(12)
        stw     .D2T1   a11, *+b15(16)
        stw     .D2T1   a12, *+b15(20)
        stw     .D2T1   a13, *+b15(24)
        stw     .D2T2   b10, *+b15(28)
        mv      .L2     b15, b10            ; b10 = Task_MIDI's stack
        mvkl    .S2     STACK_TOP, b15
        mvkh    .S2     STACK_TOP, b15
        mvkl    .S1     VARS, a10
        mvkh    .S1     VARS, a10

        FARCALL CLOCK_GETTICKS
        mv      .L1     a4, a11             ; a11 = now (ms)
        ldw     .D1T1   *+a10(V_LAST), a0
        stw     .D1T1   a11, *+a10(V_LAST)
        mvk     .S1     GAP_MS, a1
        mvk     .L1     0, a3
        nop     2
        sub     .L1     a11, a0, a0         ; ms since the previous tick
        cmpgtu  .L1     a0, a1, a2          ; first tick after a gap:
  [a2]  stw     .D1T1   a3, *+a10(V_COUNT)  ;   restart counting
  [a2]  stw     .D1T1   a3, *+a10(V_BEATS)

        ; Count ticks; only every 24th (count was 0) is a beat.
        ldw     .D1T1   *+a10(V_COUNT), a12
        mvk     .S1     24, a1
        nop     3
        add     .L1     1, a12, a0
        cmpeq   .L1     a0, a1, a2
  [a2]  mvk     .L1     0, a0
        stw     .D1T1   a0, *+a10(V_COUNT)
        mv      .L1     a12, a1
  [a1]  b       .S1     out
        nop     5

        ; Beat: shift the beat times; need two earlier beats to measure.
        ldw     .D1T1   *+a10(V_BEATS), a1
        ldw     .D1T1   *+a10(V_BEAT1), a0
        ldw     .D1T1   *+a10(V_BEAT2), a12 ; two beats ago
        nop     4
        stw     .D1T1   a0, *+a10(V_BEAT2)
        stw     .D1T1   a11, *+a10(V_BEAT1)
        mvk     .S1     2, a2
        cmplt   .L1     a1, a2, a2          ; fewer than 2 beats so far
  [a2]  add     .L1     1, a1, a1
  [a2]  stw     .D1T1   a1, *+a10(V_BEATS)
  [a2]  b       .S1     out
        nop     5

        ; bpm = (120000 + span/2) / span, span = ms for the last 2 beats
        sub     .L1     a11, a12, a12
        mvk     .S1     SPAN_MIN, a0
        cmpltu  .L1     a12, a0, a1
  [a1]  mv      .L1     a0, a12
        mvk     .S1     SPAN_MAX, a0
        cmpgtu  .L1     a12, a0, a1
  [a1]  mv      .L1     a0, a12
        shru    .S1     a12, 1, a4
        mvkl    .S1     120000, a0
        mvkh    .S1     120000, a0
        add     .L1     a0, a4, a4
        mv      .L2X    a12, b4
        FARCALL DIVU
        mv      .L1     a4, a12             ; a12 = measured bpm (40..250)

        ; Smoothing, against the tempo this code applied last (V_APPLIED).
        ; The first build compared with the tempo variable read directly and
        ; never applied on the pedal; a build without smoothing worked. So the
        ; tempo is now read the way set_setting reads it (through the
        ; setting's value pointer) and only used to notice a manual change.
        ldw     .D1T1   *+a10(V_PEND), a3
        ldw     .D1T1   *+a10(V_APPLIED), a13
        mvkl    .S1     TEMPO_SETTING, a0
        mvkh    .S1     TEMPO_SETTING, a0
        ldw     .D1T1   *a0, a0             ; value pointer
        nop     4
        ldw     .D1T1   *a0, a0             ; tempo now
        nop     4
        cmpeq   .L1     a0, a13, a1
        xor     .L1     1, a1, a2           ; tempo changed by hand (or first run)
        sub     .L1     a12, a13, a0
        abs     .L1     a0, a0
        cmpltu  .L1     1, a0, a1           ; 2 or more away
        or      .L1     a1, a2, a1
        cmpeq   .L1     a12, a3, a2         ; same 1-off value twice
        or      .L1     a1, a2, a1          ; a1 = apply now
        cmpeq   .L1     a12, a13, a2        ; already there
        or      .L1     a1, a2, a2          ; a2 = forget the pending value
        mv      .L1     a12, a3
  [a2]  mvk     .L1     0, a3
        stw     .D1T1   a3, *+a10(V_PEND)
  [!a1] b       .S1     out
        nop     5
        stw     .D1T1   a12, *+a10(V_APPLIED)

        ; Apply like tap tempo (no notification to an editor), then refresh.
        mvkl    .S1     TEMPO_SETTING, a4
        mvkh    .S1     TEMPO_SETTING, a4
        mv      .L2X    a12, b4
        mvk     .L1     0, a6
        FARCALL SET_SETTING
        FARCALL UI_REFRESH
        ldw     .D2T1   *+b14(UI_EVENT_OFS), a4
        mvk     .S2     64, b4
        FARCALL EVENT_POST

out:
        mv      .L2     b10, b15            ; back to Task_MIDI's stack
        nop     1
        ldw     .D2T2   *+b15(8), b3
        ldw     .D2T1   *+b15(12), a10
        ldw     .D2T1   *+b15(16), a11
        ldw     .D2T1   *+b15(20), a12
        ldw     .D2T1   *+b15(24), a13
        ldw     .D2T2   *+b15(28), b10
        addk    .S2     32, b15
        ldw     .D2T2   *+b14(224), b0      ; the replaced instruction
        b       .S2     b3
        nop     5
