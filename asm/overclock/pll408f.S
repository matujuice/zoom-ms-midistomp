; 408F: CPU 24 x 17 = 408 MHz, SDRAM 408 / 3 = 136 MHz, refresh 136 x 15.6 - 1.
        .equ    MULT, 17
        .equ    REFRESH, 0x848
        .include "pll.inc"
