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
;   - every 24th tick is a beat; beat times go in a ring of the last 8;
;   - from the third beat on, the last 2 beats give a quick tempo; when it
;     is 4 BPM or more from the tempo applied last on two beats in a row (or
;     nothing was applied since the clock started), it is applied and the
;     average restarts (fix6: lock in 2 beats, follow a change in 3);
;   - otherwise the average over all beats in the ring (4 to 8) is applied
;     only when it is 0.8 BPM or more from the tempo applied last (fix5):
;     every apply restarts a stock delay, and with a 2-beat measurement
;     clock jitter flipped the tempo between 140 and 141 on the pedal;
;   - tempos are kept as 10 x BPM and clamped to 40..250 BPM like tap tempo.
; Applying is what tap tempo does (0xC00B9DA8): set_setting(TEMPO, bpm), whose
; change callback takes the effect semaphore and retunes the effects, then
; Event_post(UI, 0x40) so the UI task redraws.
;
; The slow path runs on Task_MIDI's own 2 KB stack (fix3). Builds up to fix2
; switched to a private stack in L2; the pedal froze when the tempo changed
; with a delay on, i.e. when the delay's own tempo code ran on that stack.
; Stock Program Change already loads whole patches from Task_MIDI on its own
; stack, so that is the context the effects are used to.

        .equ    CLOCK_GETTICKS, 0xC00DF360  ; SYS/BIOS Clock_getTicks, 1 ms
        .equ    DIVU, 0xC00DCA20            ; a4 = a4 / b4 (unsigned), RTS
        .equ    SET_SETTING, 0xC00CAC64     ; (setting, value, notify)
        .equ    TEMPO_SETTING, 0xC00EE3D8   ; value ptr, min 40, max 250
        .equ    EVENT_POST, 0xC00CC680
        .equ    UI_EVENT_OFS, 676
        .equ    VARS, 0x1181E3C0            ; 64 zero bytes, clock_vars section
        .equ    V_COUNT, 0                  ; ticks since the last beat (0..23)
        .equ    V_LAST, 4                   ; time of the last tick
        .equ    V_BEATS, 8                  ; beats seen since restart (0..8)
        .equ    V_IDX, 12                   ; next slot in the beat ring (0..7)
        .equ    V_APPLIED10, 16             ; 10 x tempo applied last, 0 = none
        .equ    V_N, 20                     ; beats in the ring before this one
        .equ    V_JUMP, 24                  ; last beat's quick tempo was a jump
        .equ    V_RING, 32                  ; times of the last 8 beats
        .equ    HYST10, 8                   ; average: apply 0.8 BPM or more away
        .equ    JUMP10, 40                  ; 2 beats: jump 4 BPM or more away
        .equ    N_MIN, 4                    ; beats the average needs
        .equ    GAP_MS, 250
        .equ    BPM10_MIN, 400              ; 40 BPM, like tap tempo
        .equ    BPM10_MAX, 2500             ; 250 BPM

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
        nop     1                           ; fix3: stay on Task_MIDI's stack
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
  [a2]  stw     .D1T1   a3, *+a10(V_APPLIED10) ; and apply the next tempo
  [a2]  stw     .D1T1   a3, *+a10(V_JUMP)

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

        ; Beat: ring of the last 8 beat times (n = how many it holds).
        ldw     .D1T1   *+a10(V_IDX), a1
        ldw     .D1T1   *+a10(V_BEATS), a2
        nop     4
        add     .L1     -2, a1, a0
        and     .L1     7, a0, a0
        addaw   .D1     a10, a0, a0
        ldw     .D1T1   *+a0(V_RING), a12   ; a12 = time 2 beats ago
        sub     .L1     a1, a2, a0
        and     .L1     7, a0, a0
        addaw   .D1     a10, a0, a0
        ldw     .D1T1   *+a0(V_RING), a13   ; a13 = time n beats ago
        addaw   .D1     a10, a1, a0
        stw     .D1T1   a11, *+a0(V_RING)   ; this beat
        add     .L1     1, a1, a1
        and     .L1     7, a1, a1
        stw     .D1T1   a1, *+a10(V_IDX)
        stw     .D1T1   a2, *+a10(V_N)
        mvk     .S1     8, a1
        cmplt   .L1     a2, a1, a1          ; ring not full yet
  [a1]  add     .L1     1, a2, a0
  [a1]  stw     .D1T1   a0, *+a10(V_BEATS)
        mvk     .S1     2, a1
        cmplt   .L1     a2, a1, a1          ; need two earlier beats
  [a1]  b       .S1     out
        nop     5

        ; Quick measurement over the last 2 beats: 10 x bpm =
        ; (1200000 + span/2) / span. A change of 4 BPM or more on two beats
        ; in a row is a real tempo change (the first 2-beat window after a
        ; change straddles both tempos): apply it and restart the average
        ; from this beat. The first tempo after the clock starts needs no
        ; second beat.
        sub     .L1     a11, a12, a0
  [!a0] mvk     .L1     1, a0               ; never divide by 0
        shru    .S1     a0, 1, a4
        mvkl    .S1     1200000, a1
        mvkh    .S1     1200000, a1
        add     .L1     a1, a4, a4
        mv      .L2X    a0, b4
        FARCALL DIVU
        mvk     .S1     BPM10_MIN, a0
        cmplt   .L1     a4, a0, a1
  [a1]  mv      .L1     a0, a4
        mvk     .S1     BPM10_MAX, a0
        cmpgt   .L1     a4, a0, a1
  [a1]  mv      .L1     a0, a4
        ldw     .D1T1   *+a10(V_APPLIED10), a3
        ldw     .D1T1   *+a10(V_JUMP), a2
        mvk     .S1     JUMP10, a1
        nop     3
        sub     .L1     a4, a3, a0
        abs     .L1     a0, a0
        cmplt   .L1     a0, a1, a1          ; a1 = no jump
        cmpeq   .L1     0, a3, a0           ; nothing applied since the start
        or      .L1     a0, a2, a2          ; a2 = jump confirmed
        xor     .L1     1, a1, a0           ; a0 = jump now
        xor     .L1     1, a2, a3
        and     .L1     a0, a3, a3          ; jump not confirmed yet
        stw     .D1T1   a3, *+a10(V_JUMP)
  [a1]  b       .S1     steady
        nop     5
  [!a2] b       .S1     out                 ; wait for the next beat
        nop     5
        mvk     .L1     1, a0
        stw     .D1T1   a0, *+a10(V_BEATS)  ; the average starts again here
        mv      .L1     a4, a12
        b       .S1     apply
        nop     5

        ; Steady tempo: average over all n beats in the ring (4 to 8),
        ; 10 x bpm = (n x 600000 + span/2) / span, applied only when it is
        ; 0.8 BPM or more from the tempo applied last. Each apply restarts
        ; a stock delay, and with 2 beats clock jitter flipped 140/141 BPM.
steady:
        ldw     .D1T1   *+a10(V_N), a1
        mvk     .S1     9375, a3            ; 600000 = 9375 << 6
        mvk     .S1     N_MIN, a0
        nop     2
        cmplt   .L1     a1, a0, a2
  [a2]  b       .S1     out
        nop     5
        mpyu    .M1     a1, a3, a4
        sub     .L1     a11, a13, a0
  [!a0] mvk     .L1     1, a0
        shl     .S1     a4, 6, a4
        shru    .S1     a0, 1, a3
        add     .L1     a3, a4, a4
        mv      .L2X    a0, b4
        FARCALL DIVU
        mvk     .S1     BPM10_MIN, a0
        cmplt   .L1     a4, a0, a1
  [a1]  mv      .L1     a0, a4
        mvk     .S1     BPM10_MAX, a0
        cmpgt   .L1     a4, a0, a1
  [a1]  mv      .L1     a0, a4
        ldw     .D1T1   *+a10(V_APPLIED10), a0
        mvk     .S1     HYST10, a1
        nop     3
        sub     .L1     a4, a0, a0
        abs     .L1     a0, a0
        cmplt   .L1     a0, a1, a1
  [a1]  b       .S1     out
        nop     5
        mv      .L1     a4, a12

apply:  ; a12 = 10 x tempo
        add     .L1     5, a12, a4          ; bpm = (bpm10 + 5) / 10
        mvk     .S2     10, b4
        FARCALL DIVU
        mv      .L1     a4, a12             ; a12 = tempo to apply (40..250)
        shl     .S1     a12, 3, a0
        shl     .S1     a12, 1, a1
        add     .L1     a0, a1, a0
        stw     .D1T1   a0, *+a10(V_APPLIED10)

        ; Apply like tap tempo (no notification to an editor), then wake the
        ; UI task to redraw. No direct UI_REFRESH here (fix2): fix1 froze the
        ; pedal on a tempo change with a delay on, and drawing from Task_MIDI
        ; while the UI task redraws the delay's synced time is the suspect.
        mvkl    .S1     TEMPO_SETTING, a4
        mvkh    .S1     TEMPO_SETTING, a4
        mv      .L2X    a12, b4
        mvk     .L1     0, a6
        FARCALL SET_SETTING
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
