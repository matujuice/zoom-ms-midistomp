; MS-70CDR stereo input (TEST BUILD, MS-70CDR only), MS-50G 3.10 OS.
; Loaded at 0xC00F2800 (DDR RAM test region 1, after looper.S). Design: docs/ms70cdr-port.md,
; "Stereo input patch (test build)".
;
; boot (0xC00F2800), called at 0xC00D47F8 in place of the McASP init 0xC00C31A4, after the
; EDMA init and before the McASP init enables the McASP EDMA events:
;   - McASP SRCTL4 = 0x0E (AXR4 receives), RINTCTL = 0 (moved here from the McASP init)
;   - RX PaRAM 0/66/67 as on the 70CDR: SRC = DMA port 0x01D02000, ACNT 8, BCNT 16,
;     SRCBIDX 0, DSTBIDX 8; DST = BUFA, BUFA, BUFB (the OS sets 0 -> A, 66 -> A, 67 -> B)
;   - zeroes the RX buffers and the input state, then calls the McASP init.
;
; stereo_in (0xC00F2900), jumped to from the L2 audio call list (0x1181BD6C) instead of the
; three MS-50G calls rx_deint, in_combine, to_float; jumps back to 0x1181BD78.
;   Port of the MS-70CDR stages rx_deint 0x1181BB0C, in_combine 0x1181B680 (its 9
;   coefficients from 0xC00EC528) and to_float 0x1181B8C0, fused, not software-pipelined:
;   L on the A side, R on the B side, in parallel. Per frame of 4 words (w0 AXR4 s0,
;   w1 AXR5 s0, w2 AXR4 s1, w3 AXR5 s1): L uses x0 = -w1, x1 = -w3 (AXR5 pair), R uses
;   x0 = -w0, x1 = -w2 (AXR4 pair). For each side:
;     env  = c4*env + c3*|x1|                    (smpy32, plain add)
;     peak = max(c0*peak, env)
;     d    = max(0, peak - c1)                   (ssub, then the sadd/add 0x80000000 trick)
;     g    = sshl(c2*d, 8);  h = |g - 0x7FFFFFFF|
;     y    = sadd(g*x1, h*(c8*x0))               (dual-range crossfade)
;     z    = sshl(sadd(sadd(c5*y, c6*y'), c7*z'), 2)   (DC blocker)
;     out  = intsp(z) * 2^-31
;   Chain inputs: L 0x11F03638, R 0x11F03658; 0x11F03758 = the side with the larger peak
;   (L when equal), as the 70CDR writes its third array.
; Uses only caller-saved registers (A0-A9, A16-A31, B0-B9, B16-B31); the call list saves
; nothing across its calls.

        .equ    BUFA, 0x11F03B80              ; RX ping buffer, 0x80 bytes (free L1D)
        .equ    BUFB, 0x11F03C00              ; RX pong buffer, 0x80 bytes
        .equ    STATE, 0x11F03C80              ; L: peak, env, y', z'; R (+16): the same
        .equ    STEND, 0x11F03CA0
        .equ    OUT_L, 0x11F03638
        .equ    OUT_R, 0x11F03658
        .equ    OUT_MAX, 0x11F03758
        .equ    MCASP, 0x01D00000
        .equ    PARAM, 0x01C04000
        .equ    DSTREG, 0x01C0400C              ; PaRAM 0 DST: where the RX DMA writes now

        .equ    MCASP_INIT, 0xC00C31A4

        .text
        .global boot
boot:
        stw     .D2T2   b3, *b15--(8)
||      mvkl    .S1     MCASP, a4
||      mvkl    .S2     MCASP + 0x190, b4
        mvkh    .S1     MCASP, a4
||      mvkh    .S2     MCASP + 0x190, b4
||      mvk     .L1     0, a5
||      mvk     .D2     14, b5
        stw     .D1T1   a5, *+a4(124)           ; RINTCTL = 0
||      stw     .D2T2   b5, *b4                 ; SRCTL4 = 0x0E: receive
||      mvkl    .S1     PARAM, a6
||      mvkl    .S2     0x01D02000, b6
        mvkh    .S1     PARAM, a6
||      mvkh    .S2     0x01D02000, b6
        mvkl    .S1     0x00100008, a7          ; BCNT 16, ACNT 8
||      mvkl    .S2     0x00080000, b7          ; DSTBIDX 8, SRCBIDX 0
        mvkh    .S1     0x00100008, a7
||      mvkh    .S2     0x00080000, b7
        mvkl    .S1     BUFA, a8
||      mvkl    .S2     BUFB, b8
        mvkh    .S1     BUFA, a8
||      mvkh    .S2     BUFB, b8
        mvk     .S1     66 * 32, a9
||      mvk     .S2     67 * 32, b9
        add     .L1     a6, a9, a9              ; PaRAM 66
||      add     .L2X    b9, a6, b9              ; PaRAM 67
        stw     .D1T2   b6, *+a6(4)             ; PaRAM 0: SRC
        stw     .D1T1   a7, *+a6(8)             ;   A_B_CNT
        stw     .D1T1   a8, *+a6(12)            ;   DST = BUFA
        stw     .D1T2   b7, *+a6(16)            ;   SRC/DST BIDX
        stw     .D1T2   b6, *+a9(4)             ; PaRAM 66
        stw     .D1T1   a7, *+a9(8)
        stw     .D1T1   a8, *+a9(12)            ;   DST = BUFA
        stw     .D1T2   b7, *+a9(16)
        stw     .D2T2   b6, *+b9(4)             ; PaRAM 67
        stw     .D2T1   a7, *+b9(8)
        stw     .D2T2   b8, *+b9(12)            ;   DST = BUFB
        stw     .D2T2   b7, *+b9(16)
||      mvk     .S1     (STEND - BUFA) / 4, a1
zero:
        sub     .S1     a1, 1, a1
||      stw     .D1T1   a5, *a8++               ; a8 = BUFA, a5 = 0
  [a1]  b       .S1     zero
        nop     5
        mvkl    .S2     MCASP_INIT, b4          ; call the McASP init this hook replaced
        mvkh    .S2     MCASP_INIT, b4
        b       .S2     b4
        addkpc  .S2     back, b3, 4
back:
        ldw     .D2T2   *++b15(8), b3
        nop     4
        b       .S2     b3
        nop     5

        .org    0x100
        .global stereo_in
stereo_in:
        mvkl    .S1     DSTREG, a0
        mvkh    .S1     DSTREG, a0
        ldw     .D1T1   *a0, a1                 ; PaRAM 0 DST
||      mvkl    .S1     BUFA + 4, a3
||      mvkl    .S2     BUFB, b5
        mvkh    .S1     BUFA + 4, a3
||      mvkh    .S2     BUFB, b5
        mvkl    .S1     0x7FF60000, a16         ; c0
||      mvkl    .S2     0x7FF60000, b16
        mvkh    .S1     0x7FF60000, a16
||      mvkh    .S2     0x7FF60000, b16
        mvkl    .S1     0x03000000, a17         ; c1
||      mvkl    .S2     0x03000000, b17
        mvkh    .S1     0x03000000, a17
||      mvkh    .S2     0x03000000, b17
        cmpgtu  .L2X    b5, a1, b0              ; DMA still in A: process B
        mvkl    .S1     0x50000000, a18         ; c2
||      mvkl    .S2     0x50000000, b18
  [b0]  addk    .S1     0x80, a3                ; a3 = buffer + 4 (L pair)
        mvkh    .S1     0x50000000, a18
||      mvkh    .S2     0x50000000, b18
||      add     .L2X    -4, a3, b5              ; b5 = buffer (R pair)
        mvkl    .S1     0x20247A42, a19         ; c3
||      mvkl    .S2     0x20247A42, b19
        mvkh    .S1     0x20247A42, a19
||      mvkh    .S2     0x20247A42, b19
        mvkl    .S1     0x5FDB85BD, a20         ; c4
||      mvkl    .S2     0x5FDB85BD, b20
        mvkh    .S1     0x5FDB85BD, a20
||      mvkh    .S2     0x5FDB85BD, b20
        mvkl    .S1     0x1FFE3FE8, a21         ; c5
||      mvkl    .S2     0x1FFE3FE8, b21
        mvkh    .S1     0x1FFE3FE8, a21
||      mvkh    .S2     0x1FFE3FE8, b21
        mvkl    .S1     0xE001C018, a22         ; c6
||      mvkl    .S2     0xE001C018, b22
        mvkh    .S1     0xE001C018, a22
||      mvkh    .S2     0xE001C018, b22
        mvkl    .S1     0x1FFC7FD0, a23         ; c7
||      mvkl    .S2     0x1FFC7FD0, b23
        mvkh    .S1     0x1FFC7FD0, a23
||      mvkh    .S2     0x1FFC7FD0, b23
        mvkl    .S1     0x05F05F4B, a24         ; c8
||      mvkl    .S2     0x05F05F4B, b24
        mvkh    .S1     0x05F05F4B, a24
||      mvkh    .S2     0x05F05F4B, b24
        mvkl    .S1     0x80000000, a25         ; -1.0 (Q31)
||      mvkl    .S2     0x80000000, b25
        mvkh    .S1     0x80000000, a25
||      mvkh    .S2     0x80000000, b25
        mvkl    .S1     0x7FFFFFFF, a26         ; +1.0 (Q31)
||      mvkl    .S2     0x7FFFFFFF, b26
        mvkh    .S1     0x7FFFFFFF, a26
||      mvkh    .S2     0x7FFFFFFF, b26
        mvkl    .S1     0x30000000, a27         ; 2^-31 (float)
||      mvkl    .S2     0x30000000, b27
        mvkh    .S1     0x30000000, a27
||      mvkh    .S2     0x30000000, b27
        mvkl    .S1     STATE, a6
||      mvkl    .S2     STATE, b1               ; b1 = STATE until the end
        mvkh    .S1     STATE, a6
||      mvkh    .S2     STATE, b1
        ldw     .D1T1   *+a6(0), a28            ; peak
||      ldw     .D2T2   *+b1(16), b28
||      mvkl    .S1     OUT_L, a4
||      mvkl    .S2     OUT_R, b4
        ldw     .D1T1   *+a6(4), a29            ; env
||      ldw     .D2T2   *+b1(20), b29
||      mvkh    .S1     OUT_L, a4
||      mvkh    .S2     OUT_R, b4
        ldw     .D1T1   *+a6(8), a30            ; y'
||      ldw     .D2T2   *+b1(24), b30
||      mvkl    .S1     OUT_MAX, a5
        ldw     .D1T1   *+a6(12), a31           ; z'
||      ldw     .D2T2   *+b1(28), b31
||      mvkh    .S1     OUT_MAX, a5
||      mvk     .L1     8, a1                   ; frames
        nop     4

; One frame per pass, 50 cycles; cN = cycle in the pass (results of ldw at +5,
; smpy32/intsp/mpysp at +4).
loop:
        ldw     .D1T1   *+a3(0), a6             ; c0  raw x0
||      ldw     .D2T2   *+b5(0), b6
        ldw     .D1T1   *+a3(8), a7             ; c1  raw x1
||      ldw     .D2T2   *+b5(8), b7
||      addk    .S1     16, a3
||      addk    .S2     16, b5
        smpy32  .M1     a28, a16, a8            ; c2  t = c0*peak
||      smpy32  .M2     b28, b16, b8
        smpy32  .M1     a29, a20, a9            ; c3  c4*env
||      smpy32  .M2     b29, b20, b9
        nop     1
        smpy32  .M1     a6, a25, a6             ; c5  x0 = -raw
||      smpy32  .M2     b6, b25, b6
        smpy32  .M1     a7, a25, a7             ; c6  x1 = -raw
||      smpy32  .M2     b7, b25, b7
        nop     2
        smpy32  .M1     a6, a24, a6             ; c9  c8*x0
||      smpy32  .M2     b6, b24, b6
        abs     .L1     a7, a2                  ; c10 |x1|
||      abs     .L2     b7, b2
        smpy32  .M1     a2, a19, a2             ; c11 c3*|x1|
||      smpy32  .M2     b2, b19, b2
        nop     3
        add     .L1     a2, a9, a29             ; c15 env
||      add     .L2     b2, b9, b29
        cmplt   .L1     a8, a29, a0             ; c16 t < env
||      cmplt   .L2     b8, b29, b0
  [!a0] mv      .L1     a8, a28                 ; c17 peak
||[a0]  mv      .S1     a29, a28
||[!b0] mv      .L2     b8, b28
||[b0]  mv      .S2     b29, b28
        ssub    .L1     a28, a17, a8            ; c18 peak - c1
||      ssub    .L2     b28, b17, b8
        sadd    .L1     a8, a25, a8             ; c19
||      sadd    .L2     b8, b25, b8
        add     .L1     a8, a25, a8             ; c20 d = max(0, peak - c1)
||      add     .L2     b8, b25, b8
        smpy32  .M1     a8, a18, a8             ; c21 c2*d
||      smpy32  .M2     b8, b18, b8
||      cmplt   .L1X    a28, b28, a0            ;     louder: peak L < peak R
        nop     3
        sshl    .S1     a8, 8, a8               ; c25 g
||      sshl    .S2     b8, 8, b8
        ssub    .L1     a8, a26, a9             ; c26 g - 1
||      ssub    .L2     b8, b26, b9
||      smpy32  .M1     a8, a7, a7              ;     g*x1
||      smpy32  .M2     b8, b7, b7
        abs     .L1     a9, a9                  ; c27 h = 1 - g
||      abs     .L2     b9, b9
        smpy32  .M1     a9, a6, a9              ; c28 h*c8*x0
||      smpy32  .M2     b9, b6, b9
        smpy32  .M1     a30, a22, a2            ; c29 c6*y'
||      smpy32  .M2     b30, b22, b2
        smpy32  .M1     a31, a23, a6            ; c30 c7*z'
||      smpy32  .M2     b31, b23, b6
        nop     1
        sadd    .L1     a7, a9, a30             ; c32 y
||      sadd    .L2     b7, b9, b30
        smpy32  .M1     a30, a21, a7            ; c33 c5*y
||      smpy32  .M2     b30, b21, b7
        nop     3
        sadd    .L1     a7, a2, a7              ; c37
||      sadd    .L2     b7, b2, b7
        sadd    .L1     a7, a6, a7              ; c38
||      sadd    .L2     b7, b6, b7
        sshl    .S1     a7, 2, a31              ; c39 z
||      sshl    .S2     b7, 2, b31
        intsp   .L1     a31, a7                 ; c40
||      intsp   .L2     b31, b7
||      sub     .S1     a1, 1, a1
        nop     3
        mpysp   .M1     a7, a27, a7             ; c44 float out
||      mpysp   .M2     b7, b27, b7
||[a1]  b       .S1     loop                    ;     taken after c49
        nop     3
        stw     .D1T1   a7, *a4++               ; c48 L
||      stw     .D2T2   b7, *b4++               ;     R
||[!a0] mv      .L1     a7, a8
||[a0]  mv      .S1X    b7, a8
        stw     .D1T1   a8, *a5++               ; c49 louder side

        mvkl    .S2     0x1181BD78, b0          ; back to the L2 call list
||      stw     .D2T2   b31, *+b1(28)           ; save the state
        mvkh    .S2     0x1181BD78, b0
||      stw     .D2T1   a28, *+b1(0)
        b       .S2     b0
||      stw     .D2T1   a29, *+b1(4)
        stw     .D2T1   a30, *+b1(8)
        stw     .D2T1   a31, *+b1(12)
        stw     .D2T2   b28, *+b1(16)
        stw     .D2T2   b29, *+b1(20)
        stw     .D2T2   b30, *+b1(24)
