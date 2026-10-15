; Far jump from DDR to looper.S's hold_pre (v2.0 step 2). Replaces the
; target of the footswitch hold trampoline at 0xC00D46B0 (70CDR 0xC00DB590; tempo-hold.yaml); the call site and B3 are unchanged,
; and hold_pre goes on to the old target. Clobbers B0 (caller-saved).
        .text
        .global hold_pre_trampoline
hold_pre_trampoline:
        mvkl    .S2     0xC00F2210, b0
        mvkh    .S2     0xC00F2210, b0
        b       .S2     b0
        nop     5
