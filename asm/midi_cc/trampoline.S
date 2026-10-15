; Far jump from DDR to the MIDI CC handler (CC_HANDLER, os.inc).
; Placed at 0xC00AF408 (MS-50G 3.10; 0xC00E1F70 on the MS-70CDR 2.10): zero
; bytes after a function's return, never a branch target. The CC call site
; (callp at 0xC00AF088; 70CDR 0xC00AEE6C) is retargeted here; B3 still holds the return address into Task_MIDI, so the handler
; returns straight to the caller. Clobbers B0 (caller-saved).
        .include "os.inc"
        .text
        .global trampoline
trampoline:
        mvkl    .S2     CC_HANDLER, b0
        mvkh    .S2     CC_HANDLER, b0
        b       .S2     b0
        nop     5
