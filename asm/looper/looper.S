; Looper services (v2.0 step 2), MS-50G 3.10 OS.
;
; The Looper ZDL claims the services block (services.inc) with its params
; pointer and beats a heartbeat every audio block. This code, reached from
; four existing trampolines (looper.yaml), does the firmware's part:
;   poll_pre   16 ms round of Task_SwitchNrmlSpdRead, after the transport
;              poll: frees a claim whose heartbeat stopped, finds the
;              claimant's slot, works out whether the looper is under the
;              cursor in play mode (S_MINE), publishes the LED's GPIO
;              registers, and hands the LED back to the LED task when the
;              cursor leaves the looper.
;   toggle_pre footswitch press on slot A4: on the looper's slot it counts
;              a press instead of flipping the effect (no flip, no AUTO SAVE).
;   hold_pre   footswitch hold (event 224): nothing while on the looper.
;   cc_pre     MIDI CC: the looper slot's on/off CC (10n+4) counts a press
;              for values 64-127 and is dropped for 0-63.
;   draw_pre   every screen draw, before the LCD send (call at 0xC00BA9CC):
;              on the looper's Effect View, the status box top right (x 79-127,
;              y 0-9): the ZDL's 8 characters on a dither fill that follows its
;              pulse level (0/25/50/75/100 %), the text drawn as the fill's
;              negative with a solid 1-pixel edge. The poll asks the UI for a
;              redraw when the text or the fill step changes.
; Everything else goes on to the hooks the trampolines called before.
; Design and addresses: docs/os-reverse-engineering.md, "Looper services".
;
; In DDR at 0xC00F2200, RAM test region 1, after scroll.S.

        .include "services.inc"
        .equ    POLL_HOOK, 0x1181E800       ; poll.S (transport upkeep), returns A4 = ticks
        .equ    TOGGLE_HOOK, 0x1181FA98     ; hold.S toggle_hook (MOMENTARY), then the flip
        .equ    HOLD_HOOK, 0x1181FF20       ; hold2.S hold_hook, then the stock hold
        .equ    CC_HANDLER, 0x1181DEA0      ; midi_cc handler.S

        .macro  FCALL target
        mvkl    .S2     \target, b5
        mvkh    .S2     \target, b5
        b       .S2     b5
        addkpc  .S2     ret\@, b3, 4
ret\@:
        .endm

        .macro  JUMP target
        mvkl    .S2     \target, b0
        mvkh    .S2     \target, b0
        b       .S2     b0
        nop     5
        .endm

        .text
        .nocmp
vectors:
        b       .S2     poll_pre            ; +0
        nop     5
        b       .S2     toggle_pre          ; +8
        nop     5
        b       .S2     hold_pre            ; +16
        nop     5
        b       .S2     cc_pre              ; +24
        nop     5
        b       .S2     draw_pre            ; +32
        nop     5

; Called instead of poll.S; same contract: returns A4 = ticks, keeps every
; callee-saved register. Uses A0-A9, B0-B9.
poll_pre:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(4)
        mvkl    .S2     POLL_HOOK, b5
        mvkh    .S2     POLL_HOOK, b5
        b       .S2     b5
        addkpc  .S2     polled, b3, 4
polled:
        stw     .D2T1   a4, *+b15(8)
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_CLAIM), a1
        ldw     .D1T1   *+a0(S_HB), a2
        ldw     .D1T1   *+a0(S_LASTHB), a3
        ldw     .D1T1   *+a0(S_STALE), a5
        nop     4
        stw     .D1T1   a2, *+a0(S_LASTHB)
        cmpeq   .L1     a2, a3, a6          ; no audio block since the last poll
        mv      .L2X    a6, b0
  [!b0] mvk     .L1     0, a5
  [b0]  add     .L1     1, a5, a5
        stw     .D1T1   a5, *+a0(S_STALE)
        cmplt   .L1     STALE_POLLS - 1, a5, a7
        mv      .L2X    a7, b0
  [b0]  mvk     .L1     0, a1               ; the looper is gone: free its claim
  [b0]  stw     .D1T1   a1, *+a0(S_CLAIM)

        ; the claimant's slot: the state block whose word 1 is its params pointer
        mvk     .L2     -1, b1
        mvkl    .S1     SLOT_STATE, a8
        mvkh    .S1     SLOT_STATE, a8
        mvk     .L1     0, a9
  [!a1] b       .S1     slot_done
        nop     5
slot_loop:
        ldw     .D1T1   *a8, a3
        nop     4
        cmpeq   .L1     a3, a1, a2
  [a2]  mv      .L2X    a9, b1
        addk    .S1     SLOT_STRIDE, a8
        add     .L1     1, a9, a9
        cmpgt   .L1     6, a9, a2
  [a2]  b       .S1     slot_loop
        nop     5
slot_done:
        stw     .D1T2   b1, *+a0(S_SLOT)

        ; the LED: GPIO pin 0, active low (the LED task writes 1 - "lit")
        mvkl    .S1     GPIO_BANK01, a3
        mvkh    .S1     GPIO_BANK01, a3
        ldw     .D1T1   *a3, a3
        mvk     .L1     1, a5
        nop     3
        add     .D1     a3, 28, a2          ; CLR_DATA: pin low, lit
        add     .D1     a3, 24, a4          ; SET_DATA: pin high, dark
        stw     .D1T1   a2, *+a0(S_LEDON)
        stw     .D1T1   a4, *+a0(S_LEDOFF)
        stw     .D1T1   a5, *+a0(S_LEDMASK)

        ; under the cursor in play mode?
        ldw     .D2T2   *+b14(MODE), b2
        mvkl    .S1     CURSOR, a3
        mvkh    .S1     CURSOR, a3
        ldb     .D1T1   *a3, a3
        nop     4
        shl     .S1     a3, 4, a4
        shl     .S1     a3, 3, a5
        add     .L1     a4, a5, a4          ; 24 x cursor
        mvkl    .S1     CURSOR_SLOT, a5
        mvkh    .S1     CURSOR_SLOT, a5
        add     .L1     a4, a5, a4
        ldw     .D1T1   *a4, a4
        nop     4
        cmpeq   .L1X    a4, b1, a6          ; cursor slot is the looper's
        cmpeq   .L2     0, b2, b0           ; play mode
        mv      .L1X    b0, a2
        and     .L1     a6, a2, a6
        cmpgt   .L2     0, b1, b0           ; no looper
  [b0]  mvk     .L1     0, a6
        ldw     .D1T1   *+a0(S_WASMINE), a7
        stw     .D1T1   a6, *+a0(S_MINE)
        stw     .D1T1   a6, *+a0(S_WASMINE)
        nop     2
        andn    .L1     a7, a6, a7          ; was on the looper, isn't now
        mv      .L2X    a7, b0
  [!b0] b       .S1     poll_redraw
        nop     5
        ; flip the LED task's "written" bit so it writes the LED again
        mvkl    .S1     LED_APPLIED, a3
        mvkh    .S1     LED_APPLIED, a3
        ldw     .D1T1   *a3, a4
        nop     4
        xor     .L1     1, a4, a4
        stw     .D1T1   a4, *a3
poll_redraw:
        ; on the looper: redraw when the status text or the box's fill step changed
        ldw     .D1T1   *+a0(S_MINE), a1
        nop     4
  [!a1] b       .S1     poll_out
        nop     5
        ldw     .D1T1   *+a0(S_TEXT), a3
        ldw     .D1T1   *+a0(S_TEXT + 4), a4
        ldw     .D1T1   *+a0(S_LEVEL), a5
        ldw     .D1T1   *+a0(S_DTEXT), a6
        ldw     .D1T1   *+a0(S_DTEXT + 4), a7
        ldw     .D1T1   *+a0(S_DSTEP), a8
        nop     4
        add     .L1     4, a5, a5
        shr     .S1     a5, 3, a5           ; fill step 0-4
        cmpeq   .L1     a3, a6, a1
        cmpeq   .L1     a4, a7, a2
        and     .L1     a1, a2, a1
        cmpeq   .L1     a5, a8, a2
        and     .L1     a1, a2, a1
  [a1]  b       .S1     poll_out
        nop     5
        stw     .D1T1   a3, *+a0(S_DTEXT)
        stw     .D1T1   a4, *+a0(S_DTEXT + 4)
        stw     .D1T1   a5, *+a0(S_DSTEP)
        ldw     .D2T1   *+b14(UI_EVENT), a4
        mvk     .S2     EV_REDRAW, b4
        nop     3
        FCALL   EVENT_POST
poll_out:
        ldw     .D2T1   *+b15(8), a4
        ldw     .D2T2   *+b15(4), b3
        nop     4
        addk    .S2     16, b15
        b       .S2     b3
        nop     5

; S_PRESS += 1 with interrupts off (Task_MIDI and the UI task both count).
; A0 = SV. Uses A3, B6, B7.
        .macro  COUNT_PRESS
        mvc     .S2     csr, b6
        and     .L2     -2, b6, b7
        mvc     .S2     b7, csr
        ldw     .D1T1   *+a0(S_PRESS), a3
        nop     4
        add     .L1     1, a3, a3
        stw     .D1T1   a3, *+a0(S_PRESS)
        mvc     .S2     b6, csr
        .endm

; Footswitch press flips slot A4 (B3 = return).
toggle_pre:
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_SLOT), a1
        nop     4
        cmpeq   .L1     a1, a4, a2
  [a2]  b       .S1     toggle_press
        nop     5
        JUMP    TOGGLE_HOOK
toggle_press:
        COUNT_PRESS
        b       .S2     b3
        nop     5

; Footswitch hold timer (event 224, A4): nothing on the looper.
hold_pre:
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_MINE), a1
        nop     4
  [a1]  mvk     .L1     0, a4
  [a1]  b       .S2     b3
        nop     5
        JUMP    HOLD_HOOK

; MIDI CC (A6 = number, B6 = value; A4, B4, A6, B6 and B3 go on untouched).
cc_pre:
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_SLOT), a1
        nop     4
        shl     .S1     a1, 3, a2
        shl     .S1     a1, 1, a3
        add     .L1     a2, a3, a2
        add     .L1     14, a2, a2          ; 10 x slot + 14: the slot's on/off CC
        cmpeq   .L1     a2, a6, a2
        cmpgt   .L2X    0, a1, b0
  [b0]  mvk     .L1     0, a2               ; no looper
  [a2]  b       .S1     cc_ours
        nop     5
        JUMP    CC_HANDLER
cc_ours:
        shru    .S2     b6, 6, b0           ; 64-127 is a press
  [!b0] b       .S2     b3
        nop     5
        COUNT_PRESS
        b       .S2     b3
        nop     5

; Called instead of 0xC00B5794 (A4 = its argument, B3 = return) after every
; screen draw, before the LCD send. On the looper's Effect View with no overlay
; or prompt, draws the status box; then on to 0xC00B5794. Uses A0-A9, A16-A29,
; B0-B5, B16-B22 (caller-saved).
draw_pre:
        addk    .S2     -80, b15            ; +4 B3, +8 A4, +16 one byte a column
        stw     .D2T2   b3, *+b15(4)
        stw     .D2T1   a4, *+b15(8)
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_MINE), a1
        ldw     .D2T2   *+b14(PENDING), b0
        nop     4
  [b0]  mvk     .L1     0, a1
  [!a1] b       .S1     draw_out
        nop     5
        mvk     .L1     0, a4
        FCALL   OVL_GET
        cmpeq   .L1     -1, a4, a1          ; no overlay (tempo box, tuner ...)
  [!a1] b       .S1     draw_out
        nop     5

        ; the text's pixels, one byte a column (y 1-7), x 78-128 (text at 80-127)
        mvkl    .S1     SV + S_TEXT, a16
        mvkh    .S1     SV + S_TEXT, a16
        mvkl    .S1     FONT, a17
        mvkh    .S1     FONT, a17
        add     .D2     b15, 16, b16
        mvk     .L1     0, a18
        mvk     .S2     50, b18
        stb     .D2T1   a18, *b16
        stb     .D2T1   a18, *+b16(1)
        stb     .D2T1   a18, *+b16[b18]
        add     .D2     b16, 2, b17
        mvk     .L1     8, a2
ch_loop:
        ldbu    .D1T1   *a16++, a19
        nop     4
        shl     .S1     a19, 2, a20
        shl     .S1     a19, 1, a21
        add     .L1     a20, a21, a20
        add     .L1     a17, a20, a20       ; FONT + 6 x code
        mvk     .L1     6, a1
col_loop:
        ldbu    .D1T1   *a20++, a22
        nop     4
        shl     .S1     a22, 1, a22
        stb     .D2T1   a22, *b17++
        sub     .L1     a1, 1, a1
  [a1]  b       .S1     col_loop
        nop     5
        sub     .L1     a2, 1, a2
  [a2]  b       .S1     ch_loop
        nop     5

        ; fill: (even column, odd column) patterns for steps 0-4 of the level
        mvkl    .S1     SV, a0
        mvkh    .S1     SV, a0
        ldw     .D1T1   *+a0(S_LEVEL), a3
        nop     4
        add     .L1     4, a3, a3
        shr     .S1     a3, 3, a3
        mvk     .L1     0, a24
        mvk     .L1     0, a25
        mvk     .L1     0, a26
        cmplt   .L1     0, a3, a1           ; 25 %
  [a1]  mvk     .S1     0x155, a24
        cmplt   .L1     1, a3, a1           ; 50 %
  [a1]  mvk     .S1     0x2AA, a25
        cmplt   .L1     2, a3, a1           ; 75 %: dark, white text
  [a1]  mvk     .S1     0x3FF, a24
  [a1]  mvk     .S1     0x155, a25
  [a1]  mvk     .L1     1, a26
        cmplt   .L1     3, a3, a1           ; 100 %
  [a1]  mvk     .S1     0x3FF, a25

        ; each column: rows 0 (y 0-7) and bits 0-1 of row 1 (y 8-9)
        mvkl    .S1     FB + BOX_X, a27
        mvkh    .S1     FB + BOX_X, a27
        mvkl    .S1     FB + 128 + BOX_X, a29
        mvkh    .S1     FB + 128 + BOX_X, a29
        mvk     .L1     1, a28              ; x 79 is odd
        mvk     .S2     128 - BOX_X, b0
px_loop:
        ldbu    .D2T2   *b16, b18
        ldbu    .D2T2   *+b16(1), b19       ; this column's text
        ldbu    .D2T2   *+b16(2), b20
        ldbu    .D1T1   *a29, a9
        nop     4
        add     .D2     b16, 1, b16
        or      .L2     b18, b19, b18
        or      .L2     b18, b20, b18
        shl     .S2     b18, 1, b21
        shru    .S2     b18, 1, b22
        or      .L2     b18, b21, b18
        or      .L2     b18, b22, b18       ; the edge: text grown by a pixel
        mv      .L1X    b18, a6
        mv      .L1X    b19, a7
        mv      .L1     a28, a1
  [a1]  mv      .L1     a25, a5
  [!a1] mv      .L1     a24, a5
        mv      .L1     a26, a2
  [a2]  or      .L1     a5, a6, a8          ; dark: black edge, white text
  [a2]  andn    .L1     a8, a7, a8
  [!a2] andn    .L1     a5, a6, a8          ; light: white edge, black text
  [!a2] or      .L1     a8, a7, a8
        stb     .D1T1   a8, *a27++
        shru    .S1     a8, 8, a8
        and     .L1     3, a8, a8
        mvk     .L1     3, a4
        andn    .L1     a9, a4, a9
        or      .L1     a9, a8, a9
        stb     .D1T1   a9, *a29++
        xor     .L1     1, a28, a28
        sub     .L2     b0, 1, b0
  [b0]  b       .S1     px_loop
        nop     5
        mvkl    .S1     FB_DIRTY, a3
        mvkh    .S1     FB_DIRTY, a3
        ldbu    .D1T1   *a3, a4
        nop     4
        or      .L1     3, a4, a4           ; send rows 0 and 1
        stb     .D1T1   a4, *a3
draw_out:
        ldw     .D2T2   *+b15(4), b3
        ldw     .D2T1   *+b15(8), a4
        nop     4
        addk    .S2     80, b15
        JUMP    LCD_MODE
