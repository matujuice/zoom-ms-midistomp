; Far jump from DDR to swallow_hook in L2 (hold2.S vector table), MS-50G 3.10.
; Placed at 0xC00D8B70: zero bytes after a function's return (bnop b3,5) at the
; end of a plain fetch packet, never a branch target. Called from
; 0xC00AD1F8, 0xC00AD1A8, 0xC00AD158; B3 still holds the return address. Clobbers B0 (caller-saved).
        .text
        .global swallow_trampoline
swallow_trampoline:
        mvkl    .S2     0x1181FF30, b0
        mvkh    .S2     0x1181FF30, b0
        b       .S2     b0
        nop     5
