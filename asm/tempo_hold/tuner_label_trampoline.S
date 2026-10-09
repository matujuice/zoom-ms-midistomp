; Tuner screen softkeys (0xC00BA3F4): the middle knob's label, stock blank,
; reads EXIT (stock string 0xC00E9597), MS-50G 3.10.
; Placed at 0xC00DAFD0: zero bytes after a function's return (bnop b3,5) at the
; end of a plain fetch packet, never a branch target. Called from 0xC00BA5E8
; (softkey(1, label, 0)) instead of the softkey function; B3 still holds the
; return address.
        .equ    SOFTKEY, 0xC009F8F0         ; (knob, string, 0)
        .text
        .global tuner_label_trampoline
tuner_label_trampoline:
        mvkl    .S2     0xC00E9597, b4
        mvkh    .S2     0xC00E9597, b4
        ; b .S2 SOFTKEY: gas takes no absolute branch target, so encoded by
        ; hand (displacement from this fetch packet, 0xC00DAFC0, in words)
        .word   ((((SOFTKEY - 0xC00DAFC0) >> 2) & 0x1FFFFF) << 7) | 0x12
        nop     5
