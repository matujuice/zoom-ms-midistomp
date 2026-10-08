; Far jump from DDR to the MIDI CC handler in L2 RAM.
; Placed at 0xC00AF408 (MS-50G 3.10): 24 zero bytes after a function's return,
; never a branch target. The CC call site (callp at 0xC00AF088) is retargeted
; here; B3 still holds the return address into Task_MIDI, so the handler
; returns straight to the caller. Clobbers B0 (caller-saved).
        .text
        .global trampoline
trampoline:
        mvkl    .S2     0x1181DEA0, b0
        mvkh    .S2     0x1181DEA0, b0
        b       .S2     b0
        nop     5
