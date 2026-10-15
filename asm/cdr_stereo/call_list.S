; MS-70CDR stereo input (test build), MS-50G 3.10. L2 audio call list 0x1181BD6C-0x1181BD77:
; the callps to rx_deint, in_combine and to_float become one far jump to stereo.S stereo_in,
; which jumps back to 0x1181BD78 (the next callp). Clobbers B0.
        .text
        mvkl    .S2     0xC00F2900, b0
        mvkh    .S2     0xC00F2900, b0
        bnop    .S2     b0, 5
