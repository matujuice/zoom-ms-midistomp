; McASP init, MS-50G 3.10, 0xC00C323C: was stw b1,*+a4(124) (RINTCTL = 0, the reset value;
; stereo.S boot writes it before the init). Puts RBUSEL back for XFMT: a0 = 0x000180F8.
        .text
        set     .S1     a0, 3, 3, a0
