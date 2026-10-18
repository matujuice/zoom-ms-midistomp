; Mixer Mode M2: menu ENTER (settings.S mk_enter, 0x1181F0F0, A3 = entry):
; 3 MIDI SETTINGS (screen 14), 4 MIXER (screen 15), 5 the version entry
; (screen 9); the stock handler does 0-2. The branch after these eight
; instructions goes to SET_SCREEN(A4, B4) when A1 is set.
        .text
        .nocmp
        cmplt   .L1     2, a3, a1           ; entries 3-5 are ours
        mvk     .L1     5, a0
        cmpeq   .L1     a3, a0, a2          ; the version entry
        add     .L1     11, a3, a4          ; 3 -> 14, 4 -> 15
  [a2]  mvk     .L1     9, a4
        mvk     .L2     0, b4
        nop
        nop
