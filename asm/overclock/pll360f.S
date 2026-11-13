; 360F: CPU 24 x 15 = 360 MHz, SDRAM 360 / 3 = 120 MHz, refresh 120 x 15.6 - 1.
        .equ    MULT, 15
        .equ    REFRESH, 0x74F
        .include "pll.inc"
