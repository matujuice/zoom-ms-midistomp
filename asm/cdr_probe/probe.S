; MS-70CDR detection probe (debug build only, never released), MS-50G 3.10 OS.
;
; Reached from the transport poll trampoline instead of looper.S's poll_pre
; (cdr-probe.yaml), same contract; always goes on to poll_pre with B3 intact.
; p1 found AXR4 still on the MS-70CDR too: its second ADC looks held off.
; The MS-50G OS drives GPIO 52 and 90 low, which the 70CDR OS leaves as inputs,
; so p2 first lets them go (inputs drive nothing), then samples AXR4:
;   poll 64 (about 1 s after boot): GPIO 52 and 90 -> inputs
;   poll 80 (256 ms later): AXR4 -> input, PDIN bit 4 read SAMPLES times, old
;            PDIR back; GPIO 52/90 levels read; with no AXR4 activity GPIO 52
;            and 90 go back to outputs (as the MS-50G OS set them)
; Results, in the menu strings:
;   VERSION menu entry   "T" + AXR4 transitions (5 digits)
;   version screen title  GPIO 52 level, GPIO 90 level, then samples high (5 digits)
; docs/ms70cdr-port.md.
;
; In DDR at 0xC00F2800, after looper.S. Uses A0-A9, A16-A25, B0-B2.

        .equ    POLL_PRE, 0xC00F2200        ; looper.S vector +0
        .equ    MCASP_PTR, 0x1181DE0C       ; McASP0 base pointer (McASP init 0xC00C31D8)
        .equ    PDIR, 0x14
        .equ    PDIN, 0x1C
        .equ    STR_MENU, 0xC00E94AD        ; "VERSION" in the menu list (8 bytes)
        .equ    STR_TITLE, 0xC00EBADC       ; "VERSION" version screen title (8 bytes)
        .equ    GPIO_PTR, 0x1181DE70        ; GPIO base pointer (GPIO init 0xC00CE234)
        .equ    DIR23, 0x38                 ; bank 3 = upper half: GPIO 52 = bit 20
        .equ    IN23, 0x48
        .equ    DIR45, 0x60                 ; bank 5 = upper half: GPIO 90 = bit 26
        .equ    IN45, 0x70
        .equ    FREE_AT, 64
        .equ    RUN_AT, 80
        .equ    SAMPLES, 20000

        ; val as 5 decimal digits, then NUL, at dst. Clobbers val, dst.
        .macro  DEC val, dst
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
        mvkl    .S1     GPIO_PTR, a7
        mvkh    .S1     GPIO_PTR, a7
        ldw     .D1T1   *a7, a7
        mvk     .S1     FREE_AT, a6
        cmpeq   .L1     a6, a1, a2
        nop     2
  [!a2] b       .S1     run
        nop     5
        ldw     .D1T1   *+a7(DIR23), a8     ; GPIO 52 and 90 -> inputs
        ldw     .D1T1   *+a7(DIR45), a9
        nop     4
        set     .S1     a8, 20, 20, a8
        set     .S1     a9, 26, 26, a9
        stw     .D1T1   a8, *+a7(DIR23)
        stw     .D1T1   a9, *+a7(DIR45)
        b       .S2     b0
        nop     5
run:
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

        ldw     .D1T1   *+a7(IN23), a8
        ldw     .D1T1   *+a7(IN45), a9
        mv      .L1     a22, a2
        nop     3
        extu    .S1     a8, 11, 31, a8      ; GPIO 52
        extu    .S1     a9, 5, 31, a9       ; GPIO 90
  [a2]  b       .S1     levels              ; AXR4 alive: leave 52/90 as inputs
        nop     5
        ldw     .D1T1   *+a7(DIR23), a5
        ldw     .D1T1   *+a7(DIR45), a6
        nop     4
        clr     .S1     a5, 20, 20, a5
        clr     .S1     a6, 26, 26, a6
        stw     .D1T1   a5, *+a7(DIR23)
        stw     .D1T1   a6, *+a7(DIR45)
levels:

        mvkl    .S1     STR_MENU, a21
        mvkh    .S1     STR_MENU, a21
        mvk     .S1     0x54, a16           ; "T"
        stb     .D1T1   a16, *a21++
        DEC     a22, a21
        mvkl    .S1     STR_TITLE, a21
        mvkh    .S1     STR_TITLE, a21
        mvk     .S1     0x30, a16           ; "0"/"1"
        add     .L1     a16, a8, a8
        add     .L1     a16, a9, a9
        stb     .D1T1   a8, *a21++
        stb     .D1T1   a9, *a21++
        DEC     a23, a21

        mvkl    .S2     POLL_PRE, b0
        mvkh    .S2     POLL_PRE, b0
        b       .S2     b0
        nop     5

        .align  4
pow:
        .word   10000, 1000, 100, 10, 1
polls:
        .word   0
