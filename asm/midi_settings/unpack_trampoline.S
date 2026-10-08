; Far jump from DDR to unpack_hook in L2 (settings.S vector table), MS-50G 3.10.
; Placed at 0xC00BDB44: zero bytes after a function's return (bnop b3,5) at the
; end of a plain fetch packet, never a branch target. Called from
; the stock unpack call in the boot-time settings load (0xC00BA09C); B3 still holds the return address. Clobbers B0 (caller-saved).
        .text
        .global unpack_trampoline
unpack_trampoline:
        mvkl    .S2     0x1181EA20, b0
        mvkh    .S2     0x1181EA20, b0
        b       .S2     b0
        nop     5
