; Far jump from DDR to looper.S's cc_pre (v2.0 step 2). Replaces the
; target of the MIDI CC trampoline at 0xC00AF408 (70CDR 0xC00E1F70; midi-cc.yaml); the call site and B3 are unchanged,
; and cc_pre goes on to the old target. Clobbers B0 (caller-saved).
        .text
        .global cc_pre_trampoline
cc_pre_trampoline:
        mvkl    .S2     0xC00F2218, b0
        mvkh    .S2     0xC00F2218, b0
        b       .S2     b0
        nop     5
