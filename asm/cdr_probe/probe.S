; MS-70CDR detection probe (debug build only, never released), MS-50G 3.10 OS.
;
; Reached from the transport poll trampoline instead of looper.S's poll_pre
; (cdr-probe.yaml), same contract; always goes on to poll_pre with B3 intact.
; On the 64th poll (about 1 s after boot, audio running) it switches McASP pin
; AXR4 to input for one sampling run, reads PDIN bit 4 SAMPLES times, puts the
; old PDIR back and writes the result into the menu strings:
;   VERSION menu entry  "T" + transitions (5 digits)
;   version screen title "H" + samples read high (5 digits)
; On an MS-50G/60B AXR4 is a parked output (expect T00000); on an MS-70CDR it
; is the second ADC's data line (expect many transitions). docs/ms70cdr-port.md.
;
; In DDR at 0xC00F2800, after looper.S. Uses A0-A9, A16-A25, B0-B2.

        .equ    POLL_PRE, 0xC00F2200        ; looper.S vector +0
        .equ    MCASP_PTR, 0x1181DE0C       ; McASP0 base pointer (McASP init 0xC00C31D8)
        .equ    PDIR, 0x14
        .equ    PDIN, 0x1C
        .equ    STR_MENU, 0xC00E94AD        ; "VERSION" in the menu list (8 bytes)
        .equ    STR_TITLE, 0xC00EBADC       ; "VERSION" version screen title (8 bytes)
        .equ    RUN_AT, 64
        .equ    SAMPLES, 20000

        ; "<ch>" then val as 5 decimal digits, then NUL, at dst. Clobbers val, dst.
        .macro  DEC val, dst, ch
        mvk     .S1     \ch, a16
        stb     .D1T1   a16, *\dst++
        mvkl    .S1     pow, a17
        mvkh    .S1     pow, a17
        mvk     .S2     5, b2
d\@:
        ldw     .D1T1   *a17++, a18
        mvk     .S1     0x30, a19
        nop     3
s\@:
        cmplt   .L1     \val, a18, a1
  [!a1] sub     .L1     \val, a18, \val
  [!a1] add     .S1     1, a19, a19
  [!a1] b       .S2     s\@
        nop     5
        stb     .D1T1   a19, *\dst++
        sub     .L2     b2, 1, b2
  [b2]  b       .S2     d\@
        nop     5
        mvk     .S1     0, a19
        stb     .D1T1   a19, *\dst
        .endm

        .text
        .nocmp
probe:
        mvkl    .S1     polls, a0
        mvkh    .S1     polls, a0
        ldw     .D1T1   *a0, a1
        mvkl    .S2     POLL_PRE, b0
        mvkh    .S2     POLL_PRE, b0
        nop     2
        add     .L1     1, a1, a1
        stw     .D1T1   a1, *a0
        mvk     .S1     RUN_AT, a6
        cmpeq   .L1     a6, a1, a2
  [!a2] b       .S2     b0                  ; not now: straight on to poll_pre
        nop     5

        mvkl    .S1     MCASP_PTR, a3
        mvkh    .S1     MCASP_PTR, a3
        ldw     .D1T1   *a3, a3
        nop     4
        ldw     .D1T1   *+a3(PDIR), a4
        nop     4
        clr     .S1     a4, 4, 4, a5
        stw     .D1T1   a5, *+a3(PDIR)      ; AXR4 -> input
        mvkl    .S2     SAMPLES, b1
        mvkh    .S2     SAMPLES, b1
        ldw     .D1T1   *+a3(PDIN), a24     ; first read sets prev
        mvk     .S1     0, a22              ; transitions
        mvk     .S1     0, a23              ; samples high
        nop     2
        extu    .S1     a24, 27, 31, a24
loop:
        ldw     .D1T1   *+a3(PDIN), a25
        nop     4
        extu    .S1     a25, 27, 31, a25
        xor     .L1     a25, a24, a20
        add     .L1     a20, a22, a22
        add     .S1     a25, a23, a23
        mv      .L1     a25, a24
        sub     .L2     b1, 1, b1
  [b1]  b       .S2     loop
        nop     5
        stw     .D1T1   a4, *+a3(PDIR)      ; old PDIR back

        mvkl    .S1     STR_MENU, a21
        mvkh    .S1     STR_MENU, a21
        DEC     a22, a21, 0x54              ; "T"
        mvkl    .S1     STR_TITLE, a21
        mvkh    .S1     STR_TITLE, a21
        DEC     a23, a21, 0x48              ; "H"

        mvkl    .S2     POLL_PRE, b0
        mvkh    .S2     POLL_PRE, b0
        b       .S2     b0
        nop     5

        .align  4
pow:
        .word   10000, 1000, 100, 10, 1
polls:
        .word   0
