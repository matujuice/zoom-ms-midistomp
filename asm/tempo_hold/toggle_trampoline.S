; Far jump from DDR to toggle_hook in L2 (hold.S vector table), MS-50G 3.10.
; Placed at 0xC00D3370: zero bytes after a function's return (bnop b3,5) at the
; end of a plain fetch packet, never a branch target. Called from
; 0xC00ACC2C; B3 still holds the return address. Clobbers B0 (caller-saved).
        .text
        .global toggle_trampoline
toggle_trampoline:
        mvkl    .S2     0x1181FA98, b0
        mvkh    .S2     0x1181FA98, b0
        b       .S2     b0
        nop     5
