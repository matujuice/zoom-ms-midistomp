; Far jump from DDR to cdr_probe probe.S (debug build), MS-50G 3.10. Replaces the
; target of the transport poll trampoline at 0xC00C8050 (midi-clock.yaml); the call site and B3 are unchanged,
; and poll_pre goes on to the old target. Clobbers B0 (caller-saved).
        .text
        .global poll_pre_trampoline
poll_pre_trampoline:
        mvkl    .S2     0xC00F2800, b0
        mvkh    .S2     0xC00F2800, b0
        b       .S2     b0
        nop     5
