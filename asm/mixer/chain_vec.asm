; Mixer Mode M3b: fixed entry points at the start of the C section (0xC00F8000),
; linked first by scripts/build_mixer_ui.py; patches/mixer-m2.yaml and mixer.S
; name them by address. TI assembler syntax (this file goes through cl6x).
        .sect   ".vectors"
        .nocmp                          ; 32-bit only: the vectors keep their 8-byte stride
        .global chain_key, chain_draw_h, chain_poll, kp_exit, s33_keys
        B       .S2     keys_e          ; +0  screen 3 key table entry
        NOP     5
        B       .S2     draw_e          ; +8  screen 3 draw table entry
        NOP     5
        B       .S2     chain_poll      ; +16 from mixer.S poll (B3 = return)
        NOP     5
        B       .S2     kp_exit         ; +24 callp at 0xC00AC804 (knob pages EXIT)
        NOP     5
        B       .S2     s33_keys        ; +32 callp at 0xC00A832C (screens 32/33 keys)
        NOP     5

; Switch-table entries: the event pair is in the dispatcher's frame (+8 event,
; +12 knob steps); return through the dispatcher's epilogue.
keys_e:
        LDW     .D2T1   *+B15(8), A4
        LDW     .D2T2   *+B15(12), B4
        MVKL    .S2     0xC00A83C0, B3  ; KEY_DONE, A4 = redraw
        MVKH    .S2     0xC00A83C0, B3
        B       .S1     chain_key
        NOP     5
draw_e:
        MVKL    .S2     0xC00A9404, B3  ; DRAW_DONE
        MVKH    .S2     0xC00A9404, B3
        B       .S1     chain_draw_h
        NOP     5
