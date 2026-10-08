; Far jump from DDR to the transport poll in L2 RAM (issue #24).
; Placed at 0xC00C8050 (MS-50G 3.10): the 16 zero bytes after a function's
; return (bnop b3,5 at 0xC00C804C), the last four words of a plain fetch
; packet, never a branch target. Task_SwitchNrmlSpdRead's Clock_getTicks call
; at 0xC00CA630 calls here instead; B3 returns into that task.
; Clobbers B0 (caller-saved).
        .text
        .global poll_trampoline
poll_trampoline:
        mvkl    .S2     0x1181E780, b0
        mvkh    .S2     0x1181E780, b0
        b       .S2     b0
        nop     5
