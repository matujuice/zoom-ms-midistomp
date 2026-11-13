; Run-time CPU overclock: switch PLL0 before the OS starts. MS-70CDR 2.10 OS.
; Included by pll360f.S / pll408f.S, which set MULT (24 MHz x MULT = CPU MHz)
; and REFRESH (SDRAM refresh count for the new SDRAM clock).
;
; The Zoom bootloader runs only MAIN's AIS section loads, fills and the final
; jump; it skips the ROM function / SET commands, so editing the AIS PLL words
; changes nothing. Instead MAIN's AIS jumps here (loaded as a section into L2,
; free at boot: the bootloader lives in SDRAM), and this jumps to the OS entry.
;
; Sequence (C6745 PLLC0, all while running from L2 with SDRAM idle):
;   bypass -> EMIFB clock to SYSCLK5 -> reset PLL, new PLLM and dividers ->
;   lock -> enable -> SDRAM refresh count for the new clock -> OS.
; Dividers: POSTDIV /1, PLLDIV3 /4 (EMIFA), PLLDIV5 /3 (SDRAM), PLLDIV7 /8.
; SYSCLK2/4 keep their fixed ratios, so SPI/LCD/EDMA scale with the CPU.
; A pedal that hangs still recovers: update mode never runs this.

        .equ    PLL0, 0x01C11100            ; PLLC0 + 0x100 (PLLCTL)
        .equ    KICK0R, 0x01C14038
        .equ    CFGCHIP0, 0x01C1417C
        .equ    CFGCHIP3, 0x01C14188
        .equ    SDRFC, 0xB000000C
        .equ    OS_ENTRY, 0xC00DD800        ; c_int00, MAIN's stock AIS entry

        .macro  WAIT n                      ; 6 cycles per turn
        mvkl    .S2     \n, b0
        mvkh    .S2     \n, b0
w\@:    sub     .L2     b0, 1, b0
  [b0]  b       .S2     w\@
        nop     5
        .endm

        .macro  GOWAIT                      ; until PLLSTAT.GOSTAT = 0
g\@:    ldw     .D1T1   *+a4(0x3C), a2
        nop     4
        and     .L1     1, a2, a2
  [a2]  b       .S1     g\@
        nop     5
        .endm

        .macro  SETW off, val               ; *(PLL0 + off) = val
        mvkl    .S2     \val, b4
        mvkh    .S2     \val, b4
        stw     .D1T2   b4, *+a4(\off)
        .endm

        .text
        .nocmp
pll_boot:
        mvk     .S2     0, b1
        mvc     .S2     b1, IER             ; interrupts stay off (the bootloader left them off)
        mvc     .S2     b1, CSR
        mvkl    .S1     PLL0, a4
        mvkh    .S1     PLL0, a4
        mvkl    .S1     KICK0R, a5          ; unlock SYSCFG (CFGCHIP0/3)
        mvkh    .S1     KICK0R, a5
        mvkl    .S2     0x83E70B13, b4
        mvkh    .S2     0x83E70B13, b4
        stw     .D1T2   b4, *a5
        mvkl    .S2     0x95A4F1E0, b4
        mvkh    .S2     0x95A4F1E0, b4
        stw     .D1T2   b4, *+a5(4)
        mvkl    .S1     CFGCHIP0, a6        ; PLL_MASTER_LOCK off
        mvkh    .S1     CFGCHIP0, a6
        ldw     .D1T1   *a6, a2
        nop     4
        clr     .S1     a2, 4, 4, a2
        stw     .D1T1   a2, *a6

        ldw     .D1T1   *a4, a1             ; PLLCTL
        nop     4
        clr     .S1     a1, 5, 5, a1        ; PLLENSRC: PLLEN bit decides
        stw     .D1T1   a1, *a4
        clr     .S1     a1, 0, 0, a1        ; PLLEN = 0: bypass, CPU on 24 MHz
        stw     .D1T1   a1, *a4
        WAIT    100

        mvkl    .S1     CFGCHIP3, a6        ; EMIFB from SYSCLK5, not PLL / 4.5 (stock 5 -> 0)
        mvkh    .S1     CFGCHIP3, a6
        ldw     .D1T1   *a6, a2
        nop     4
        clr     .S1     a2, 0, 0, a2
        clr     .S1     a2, 2, 2, a2
        stw     .D1T1   a2, *a6

        clr     .S1     a1, 3, 3, a1        ; PLLRST = 0: PLL in reset
        stw     .D1T1   a1, *a4
        SETW    0x10, (MULT-1)            ; PLLM
        SETW    0x28, 0x8000                ; POSTDIV /1
        GOWAIT
        SETW    0x20, 0x8003                ; PLLDIV3 /4
        SETW    0x64, 0x8002                ; PLLDIV5 /3: SDRAM = CPU / 3
        SETW    0x6C, 0x8007                ; PLLDIV7 /8
        SETW    0x38, 1                     ; PLLCMD.GOSET
        GOWAIT
        WAIT    100                         ; reset time
        set     .S1     a1, 3, 3, a1        ; PLLRST = 1
        stw     .D1T1   a1, *a4
        WAIT    8000                        ; lock, about 2 ms at 24 MHz
        set     .S1     a1, 0, 0, a1        ; PLLEN = 1
        stw     .D1T1   a1, *a4

        mvkl    .S1     SDRFC, a6           ; refresh count (bits 12:0) for the new SDRAM clock
        mvkh    .S1     SDRFC, a6
        ldw     .D1T1   *a6, a2
        nop     4
        clr     .S1     a2, 0, 12, a2
        mvk     .S1     REFRESH, a3
        or      .L1     a2, a3, a2
        stw     .D1T1   a2, *a6

        mvkl    .S2     OS_ENTRY, b0
        mvkh    .S2     OS_ENTRY, b0
        b       .S2     b0
        nop     5
