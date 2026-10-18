; Mixer Mode M2: the menu draw (midi_settings settings.S menu_draw, 0x1181EF78)
; lists the mixer's six names (MENU6) instead of its five.
        .text
        .nocmp
        mvkl    .S2     0xC00F60C8, b4
        mvkh    .S2     0xC00F60C8, b4
        mvk     .L1     6, a6
