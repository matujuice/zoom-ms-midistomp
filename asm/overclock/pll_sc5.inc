; Run-time CPU overclock, SYSCLK5 variant: same as pll.inc, but switches EMIFB's SDRAM
; clock (CFGCHIP3.EMB_CLKSRC) from the stock DIV4.5 tap to PLLDIV5/SYSCLK5, following
; Aleksander Lim's recipe (he reports this works on his boards; our first attempt at it
; hung, clearing EMB_CLKSRC and DIV45PENA in the SAME write -- a glitch during the mux
; switch, not an ordering-vs-PLLDIV5 bug as first suspected):
;   1. enable PLLDIV5      2. set CFGCHIP3.DIV45PENA (keep both clocks alive)
;   3. switch EMB_CLKSRC   4. clear DIV45PENA (only now drop the now-unused DIV4.5 tap)
; Included by pll360f_sc5.S, which sets MULT (24 MHz x MULT = CPU MHz) and REFRESH
; (SDRAM refresh count for the new SDRAM clock, CPU MHz / 3).
;
; Sequence: SDRAM self-refresh -> bypass -> reset PLL, new PLLM/POSTDIV/PLLDIV3/5/7 ->
; lock -> enable -> the CFGCHIP3 switch above -> exit self-refresh -> reprogram
; SDTIM1/SDTIM2 (doubled, same conservative margin as pll.inc) -> new SDRFC.REFRESH_RATE
; -> OS. PLLDIV5 /3: SDRAM = CPU / 3 (120 MHz at 360 MHz CPU, well inside EMIFB's 152 MHz).
; A pedal that hangs still recovers: update mode never runs this.

        .equ    PLL0, 0x01C11100
        .equ    KICK0R, 0x01C14038
        .equ    CFGCHIP0, 0x01C1417C
        .equ    CFGCHIP3, 0x01C14188
        .equ    SDCFG, 0xB0000008
        .equ    SDRFC, 0xB000000C
        .equ    SDTIM1, 0xB0000010
        .equ    SDTIM2, 0xB0000014
        .equ    OS_ENTRY, 0xC00DD800

        .macro  WAIT n
        mvkl    .S2     \n, b0
        mvkh    .S2     \n, b0
w\@:    sub     .L2     b0, 1, b0
  [b0]  b       .S2     w\@
        nop     5
        .endm

        .macro  GOWAIT
g\@:    ldw     .D1T1   *+a4(0x3C), a2
        nop     4
        and     .L1     1, a2, a2
  [a2]  b       .S1     g\@
        nop     5
        .endm

        .macro  SETW off, val
        mvkl    .S2     \val, b4
        mvkh    .S2     \val, b4
        stw     .D1T2   b4, *+a4(\off)
        .endm

        .macro  FIELD hi, lo, w, maxval, src, acc
        extu    .S1     \src, (31-(\hi)), (32-(\w)), a4
        shl     .S1     a4, 1, a4
        set     .S1     a4, 0, 0, a4
        mvk     .S2     \maxval, b5
        cmpgt   .L1X    a4, b5, a2
  [a2]  mvk     .S1     \maxval, a4
        shl     .S1     a4, \lo, a4
        or      .L1     \acc, a4, \acc
        .endm

        .text
        .nocmp
pll_boot:
        mvk     .S2     0, b1
        mvc     .S2     b1, IER
        mvc     .S2     b1, CSR

        mvkl    .S1     SDRFC, a7
        mvkh    .S1     SDRFC, a7
        ldw     .D1T1   *a7, a8
        nop     4
        set     .S1     a8, 31, 31, a8      ; LP_MODE = 1
        clr     .S1     a8, 23, 23, a8      ; SR_PD = 0 -> self-refresh
        stw     .D1T1   a8, *a7
        WAIT    2000

        mvkl    .S1     PLL0, a4
        mvkh    .S1     PLL0, a4
        mvkl    .S1     KICK0R, a5          ; unlock SYSCFG (CFGCHIP0 and CFGCHIP3)
        mvkh    .S1     KICK0R, a5
        mvkl    .S2     0x83E70B13, b4
        mvkh    .S2     0x83E70B13, b4
        stw     .D1T2   b4, *a5
        mvkl    .S2     0x95A4F1E0, b4
        mvkh    .S2     0x95A4F1E0, b4
        stw     .D1T2   b4, *+a5(4)
        mvkl    .S1     CFGCHIP0, a6
        mvkh    .S1     CFGCHIP0, a6
        ldw     .D1T1   *a6, a2
        nop     4
        clr     .S1     a2, 4, 4, a2
        stw     .D1T1   a2, *a6

        ldw     .D1T1   *a4, a1             ; PLLCTL
        nop     4
        clr     .S1     a1, 5, 5, a1        ; PLLENSRC
        stw     .D1T1   a1, *a4
        clr     .S1     a1, 0, 0, a1        ; PLLEN = 0: bypass
        stw     .D1T1   a1, *a4
        WAIT    100

        clr     .S1     a1, 3, 3, a1        ; PLLRST = 0
        stw     .D1T1   a1, *a4
        SETW    0x10, (MULT-1)              ; PLLM
        SETW    0x28, 0x8000                ; POSTDIV /1
        GOWAIT
        SETW    0x20, 0x800F                ; PLLDIV3 /16 (EMIFA, conservative)
        SETW    0x64, 0x8002                ; PLLDIV5 /3 (SDRAM = CPU / 3)
        SETW    0x6C, 0x8007                ; PLLDIV7 /8
        SETW    0x38, 1                     ; PLLCMD.GOSET
        GOWAIT
        WAIT    100
        set     .S1     a1, 3, 3, a1        ; PLLRST = 1
        stw     .D1T1   a1, *a4
        WAIT    8000
        set     .S1     a1, 0, 0, a1        ; PLLEN = 1
        stw     .D1T1   a1, *a4
        WAIT    2000

        mvkl    .S1     CFGCHIP3, a6        ; Aleksander's switch, while still in self-refresh:
        mvkh    .S1     CFGCHIP3, a6        ; both clocks stay alive across the mux change.
        ldw     .D1T1   *a6, a2
        nop     4
        set     .S1     a2, 2, 2, a2        ; 1: DIV45PENA (keep DIV4.5 running too)
        stw     .D1T1   a2, *a6
        WAIT    100
        clr     .S1     a2, 0, 0, a2        ; 2: EMB_CLKSRC = 0 -> SYSCLK5 (the actual switch)
        stw     .D1T1   a2, *a6
        WAIT    100
        clr     .S1     a2, 2, 2, a2        ; 3: DIV45PENA = 0 (drop the now-unused DIV4.5 tap)
        stw     .D1T1   a2, *a6
        WAIT    2000

        clr     .S1     a8, 31, 31, a8      ; LP_MODE = 0: exit self-refresh
        stw     .D1T1   a8, *a7
        WAIT    2000

        mvkl    .S1     SDCFG, a6
        mvkh    .S1     SDCFG, a6
        ldw     .D1T1   *a6, a1
        nop     4
        set     .S1     a1, 15, 15, a2
        stw     .D1T1   a2, *a6

        mvkl    .S1     SDTIM1, a5
        mvkh    .S1     SDTIM1, a5
        ldw     .D1T1   *a5, a3
        nop     4
        mvk     .S1     0, a6
        FIELD   31, 25, 7, 0x7F, a3, a6     ; T_RFC
        FIELD   24, 22, 3, 0x7,  a3, a6     ; T_RP
        FIELD   21, 19, 3, 0x7,  a3, a6     ; T_RCD
        FIELD   18, 16, 3, 0x7,  a3, a6     ; T_WR
        FIELD   15, 11, 5, 0x1F, a3, a6     ; T_RAS
        FIELD   10, 6,  5, 0x1F, a3, a6     ; T_RC
        FIELD   5,  3,  3, 0x7,  a3, a6     ; T_RRD
        stw     .D1T1   a6, *a5

        mvkl    .S1     SDTIM2, a5
        mvkh    .S1     SDTIM2, a5
        ldw     .D1T1   *a5, a3
        nop     4
        mvkl    .S1     0x78000000, a2
        mvkh    .S1     0x78000000, a2
        and     .S1     a3, a2, a6
        FIELD   22, 16, 7, 0x7F, a3, a6     ; T_XSR
        FIELD   4,  0,  5, 0x1F, a3, a6     ; T_CKE
        stw     .D1T1   a6, *a5

        mvkl    .S1     SDCFG, a6
        mvkh    .S1     SDCFG, a6
        stw     .D1T1   a1, *a6

        ldw     .D1T1   *a7, a8
        nop     4
        clr     .S1     a8, 0, 15, a8
        mvk     .S1     REFRESH, a3
        or      .L1     a8, a3, a8
        stw     .D1T1   a8, *a7

        .ifdef  BOOTDELAY
        WAIT    BOOTDELAY
        .endif

        mvkl    .S2     OS_ENTRY, b0
        mvkh    .S2     OS_ENTRY, b0
        b       .S2     b0
        nop     5
