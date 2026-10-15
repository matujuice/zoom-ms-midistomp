; Tuner screen softkeys (50G 0xC00BA3F4, 70CDR 0xC00BAAD4): the middle knob's
; label, stock blank, reads EXIT (STR_EXIT). OS addresses: os.inc.
; Placed at TUNER_LABEL_TRAMP: zero bytes after a function's return (bnop
; b3,5) at the end of a plain fetch packet, never a branch target. Called from
; the softkey(1, label, 0) call (50G 0xC00BA5E8, 70CDR 0xC00BAD40) instead of
; the softkey function; B3 still holds the return address.
        .include "os.inc"
        .text
        .global tuner_label_trampoline
tuner_label_trampoline:
        mvkl    .S2     STR_EXIT, b4
        mvkh    .S2     STR_EXIT, b4
        ; b .S2 SOFTKEY: gas takes no absolute branch target, so encoded by
        ; hand (displacement from this fetch packet, in words)
        .word   ((((SOFTKEY - (TUNER_LABEL_TRAMP & ~31)) >> 2) & 0x1FFFFF) << 7) | 0x12
        nop     5
