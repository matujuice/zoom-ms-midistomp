; MIDI settings page (issue #26, v0.5), MS-50G 3.10 OS.
;
; Four rows at the end of the stock SETTINGS list (menu > SETTINGS), each
; opening an OFF/ON screen drawn like AUTO SAVE:
;   MIDI CLOCK        clock sets the patch tempo (v0.3)
;   MIDI START/STOP   Start/Stop and the clock count in the transport block
;   MIDI PROG CHANGE  program change loads patches
;   MIDI CC           every CC (our v0.2 map and the stock CC 0/74/75)
; All on by default, so v0.4 behaviour is unchanged.
;
; UI (see docs/os-reverse-engineering.md, "Settings screen"):
;   - screen 1 (SETTINGS list): its key handler entry in the switch table at
;     0xC00EF300 points at list_keys, which adds the four rows (11 instead of
;     7) and leaves everything else to the stock handler. The stock list draw
;     is pointed at our name and icon tables and an 11-row scrollbar by
;     three instruction patches (patches/midi-settings.yaml).
;   - screen 13 is unused by the stock OS (its table entries go to the
;     menu): it becomes our OFF/ON screen, midi_keys and midi_draw, with
;     V_ITEM saying which of the four rows it shows.
; Switch-table entries are reached by a register branch from the stock
; dispatchers, with their frame still on the stack; we return by branching
; to the dispatcher's own epilogue (KEY_DONE / DRAW_DONE) with A4 = result.
;
; Saving: the stock settings are 38 words at 0xC009D8F8, bit-packed into a
; 24-byte record (flash record 50) with 185 bits used. The OFF bits go in
; the free bits 1-4 of byte 23 (pack_hook after the stock pack, unpack_hook
; after the stock unpack at boot). A stock record has them 0 = all on.
; The stock code saves only when the 38 words differ from a shadow copy
; (0xC009D860), so a change here flips a bit of the shadow.
;
; MIDI: midi_gate sits in front of the CC and PC call sites in Task_MIDI;
; clock.S checks OFF_CLOCK and OFF_TRANSPORT itself.

        .include "../midi_clock/transport.inc"

        .equ    BASE, 0x1181EA00
        .equ    V_FLAGS, 48                 ; = MIDI_FLAGS - BASE
        .equ    V_ITEM, 52                  ; row shown on screen 13 (0..3)

        .equ    SET_SCREEN, 0xC00A75E0      ; (screen, row)
        .equ    LIST_INDEX, 0xC00A7040      ; -> row + top of the list
        .equ    LIST_SCROLL, 0xC00A72D4     ; (delta, rows)
        .equ    STOCK_LIST_KEYS, 0xC00A7904
        .equ    KEY_DONE, 0xC00A840C        ; key dispatcher epilogue, A4 = redraw
        .equ    DRAW_DONE, 0xC00A9468       ; draw dispatcher epilogue
        .equ    DRAW_TITLE, 0xC00A7378      ; (string)
        .equ    DRAW_TEXT, 0xC009FCE0       ; (0, string, 1, y)
        .equ    HILITE, 0xC00A73A4          ; (row, 0)
        .equ    DRAW_ARROWS, 0xC00A7400     ; (0)
        .equ    SOFTKEY, 0xC009F8F0         ; (knob, string, 0)
        .equ    STR_EXIT, 0xC00E9597
        .equ    STR_BLANK, 0xC00E959C
        .equ    OFF_ON, 0xC00ED238          ; "OFF", "ON"
        .equ    SHADOW, 0xC009D860
        .equ    PACK, 0xC00D3C6C
        .equ    UNPACK, 0xC00D3B80
        .equ    CC_HANDLER, 0x1181DEA0
        .equ    STOCK_CHANNEL_MSG, 0xC00AE0F8
        .equ    EV_ENTER, 34
        .equ    EV_EXIT, 65
        .equ    EV_TURN, 160
        .equ    SCREEN_LIST, 1
        .equ    SCREEN_MIDI, 13
        .equ    STOCK_ROWS, 7
        .equ    ROWS, 11

; Branch to an absolute address (B0).
        .macro  JUMP target
        mvkl    .S2     \target, b0
        mvkh    .S2     \target, b0
        b       .S2     b0
        nop     5
        .endm

        .text
        .nocmp
; Entry points at fixed offsets (the patch file names them by address).
vectors:
        b       .S2     list_keys           ; +0
        nop     5
        b       .S2     midi_keys           ; +8
        nop     5
        b       .S2     midi_draw           ; +16
        nop     5
        b       .S2     pack_hook           ; +24
        nop     5
        b       .S2     unpack_hook         ; +32
        nop     5
        b       .S2     midi_gate           ; +40
        nop     5
        .word   0                           ; +48 V_FLAGS
        .word   0                           ; +52 V_ITEM
        .word   0, 0

; +64: row names for the SETTINGS list (7 stock, then ours)
names:
        .word   0xC00E94B5, 0xC00E94C8, 0xC00E94DA, 0xC00E94EB
        .word   0xC00E94F5, 0xC00E9502, 0xC00E9510
        .word   s_clock, s_transport, s_pc, s_cc
        .word   0
; +112: 7x7 row icons, one byte per column, bit 0 at the top (stock 7
; copied from 0xC00EC5A8, then a MIDI socket for our rows)
icons:
        .byte   0x1c, 0x3e, 0x4f, 0x41, 0x7b, 0x36, 0x1c
        .byte   0x00, 0x00, 0x1f, 0x60, 0x1f, 0x00, 0x00
        .byte   0x1c, 0x22, 0x40, 0x4f, 0x40, 0x22, 0x1c
        .byte   0x70, 0x44, 0x4c, 0x5f, 0x4c, 0x44, 0x70
        .byte   0x00, 0x7e, 0x7f, 0x7f, 0x7f, 0x7e, 0x00
        .byte   0x7f, 0x41, 0x5d, 0x5d, 0x5d, 0x41, 0x7f
        .byte   0x1c, 0x22, 0x71, 0x79, 0x7d, 0x3e, 0x1c
        .rept   4
        .byte   0x1c, 0x22, 0x55, 0x41, 0x55, 0x22, 0x1c
        .endr
s_clock:        .string "MIDI CLOCK"
s_transport:    .string "MIDI START/STOP"
s_pc:           .string "MIDI PROG CHANGE"
s_cc:           .string "MIDI CC"
        .p2align 5

; Screen 1 keys. Entered from the dispatcher's switch with the event pair at
; *+B15(8): A4 = event, A5 = knob turn.
list_keys:
        lddw    .D2T1   *+b15(8), a5:a4
        nop     4
        mvk     .S1     EV_ENTER, a0
        cmpeq   .L1     a4, a0, a1
  [a1]  b       .S1     list_enter
        mvk     .S1     EV_TURN, a0
        cmpeq   .L1     a4, a0, a2
  [a2]  b       .S1     list_turn
        nop     5
list_stock:     ; the stock handler, returning straight to the epilogue
        mvkl    .S2     KEY_DONE, b3
        mvkh    .S2     KEY_DONE, b3
        JUMP    STOCK_LIST_KEYS

list_turn:
        mv      .L1     a5, a4
        mvk     .L2     ROWS, b4
        mvkl    .S2     LIST_SCROLL, b0
        mvkh    .S2     LIST_SCROLL, b0
        b       .S2     b0
        mvkl    .S2     redraw, b3
        mvkh    .S2     redraw, b3
        nop     3
redraw:
        mvk     .L1     1, a4
        JUMP    KEY_DONE

list_enter:
        mvkl    .S2     LIST_INDEX, b0
        mvkh    .S2     LIST_INDEX, b0
        b       .S2     b0
        mvkl    .S2     got_index, b3
        mvkh    .S2     got_index, b3
        nop     3
got_index:
        mvk     .S1     STOCK_ROWS, a0
        cmplt   .L1     a4, a0, a1
  [a1]  lddw    .D2T1   *+b15(8), a5:a4     ; a stock row: stock handler
  [a1]  b       .S1     list_stock
        nop     5
        sub     .L1     a4, a0, a4          ; our row 0..3
        mvkl    .S1     BASE, a0
        mvkh    .S1     BASE, a0
        stw     .D1T1   a4, *+a0(V_ITEM)
        mvk     .L1     SCREEN_MIDI, a4
        mvk     .L2     0, b4
        mvkl    .S2     SET_SCREEN, b0
        mvkh    .S2     SET_SCREEN, b0
        b       .S2     b0
        mvkl    .S2     redraw, b3
        mvkh    .S2     redraw, b3
        nop     3

; Screen 13 keys: EXIT goes back to the list on our row, a knob turn sets
; OFF (left) or ON (right), like the stock OFF/ON screens.
midi_keys:
        lddw    .D2T1   *+b15(8), a5:a4
        mvkl    .S1     BASE, a3
        mvkh    .S1     BASE, a3
        ldw     .D1T1   *+a3(V_ITEM), a6
        ldw     .D1T1   *+a3(V_FLAGS), a7
        nop     1
        mvk     .S1     EV_EXIT, a0
        cmpeq   .L1     a4, a0, a1
  [a1]  b       .S1     midi_exit
        mvk     .S1     EV_TURN, a0
        cmpeq   .L1     a4, a0, a2
  [a2]  b       .S1     midi_turn
        nop     5
        mvk     .L1     0, a4               ; other keys: nothing to do
        JUMP    KEY_DONE

midi_exit:
        add     .L1     STOCK_ROWS, a6, a0
        mv      .L2X    a0, b4
        mvk     .L1     SCREEN_LIST, a4
        mvkl    .S2     SET_SCREEN, b0
        mvkh    .S2     SET_SCREEN, b0
        b       .S2     b0
        mvkl    .S2     redraw, b3
        mvkh    .S2     redraw, b3
        nop     3

midi_turn:      ; a6 = item, a7 = flags, a5 = turn
        mvk     .L1     1, a8
        shl     .S1     a8, a6, a8          ; a8 = this row's OFF bit
        and     .L1     a8, a7, a0
        cmpeq   .L1     0, a0, a0           ; a0 = 1 if now on
        add     .L1     a0, a5, a0
        cmplt   .L1     0, a0, a1           ; a1 = new value (0..1 clamp)
        xor     .L1     1, a1, a1           ; a1 = 1 if it should be off
        and     .L1     a8, a7, a0
        cmpeq   .L1     0, a0, a0
        xor     .L1     1, a0, a0           ; a0 = 1 if off now
        cmpeq   .L1     a0, a1, a2
  [a2]  b       .S1     redraw              ; no change
        nop     5
        xor     .L1     a8, a7, a7
        stw     .D1T1   a7, *+a3(V_FLAGS)
        mvkl    .S2     SHADOW, b4          ; make the stock save see a change
        mvkh    .S2     SHADOW, b4
        ldw     .D2T2   *b4, b5
        mvk     .S2     1, b6
        shl     .S2     b6, 31, b6
        nop     2
        xor     .L2     b6, b5, b5
        stw     .D2T2   b5, *b4
        ; START/STOP turned off: the transport counts as stopped.
        and     .L1     OFF_TRANSPORT, a8, a0
        and     .L1     a1, a0, a0
  [!a0] b       .S1     redraw
        nop     5
        PUB_BEGIN
        mvk     .L1     0, a0
        stw     .D1T1   a0, *+a5(B_RUN)
        PUB_END
        b       .S1     redraw
        nop     5

; Screen 13 drawing, as the stock AUTO SAVE screen (0xC00A9270) does it.
midi_draw:
        addk    .S2     -16, b15
        stw     .D2T1   a10, *+b15(8)
        stw     .D2T1   a11, *+b15(12)
        mvkl    .S1     BASE, a10
        mvkh    .S1     BASE, a10
        ldw     .D1T1   *+a10(V_ITEM), a0
        nop     4
        addaw   .D1     a10, a0, a1
        ldw     .D1T1   *+a1(64 + 4 * STOCK_ROWS), a4   ; our row name
        nop     4
        FARCALL DRAW_TITLE
        mvk     .L1     0, a11              ; option rows OFF, ON
draw_row:
        mvkl    .S1     OFF_ON, a3
        mvkh    .S1     OFF_ON, a3
        ldw     .D1T2   *+a3[a11], b4
        mvk     .S1     9, a0
        mpy     .M1     a11, a0, a0
        mvk     .L1     0, a4
        mvk     .L1     1, a6
        add     .L1     12, a0, a0
        mv      .L2X    a0, b6
        FARCALL DRAW_TEXT
        add     .L1     1, a11, a11
        cmpgt   .L1     2, a11, a0
  [a0]  b       .S1     draw_row
        nop     5
        ldw     .D1T1   *+a10(V_ITEM), a0
        ldw     .D1T1   *+a10(V_FLAGS), a1
        nop     3
        mvk     .L1     1, a2
        shl     .S1     a2, a0, a2
        and     .L1     a2, a1, a1
        cmpeq   .L1     0, a1, a4           ; highlight ON (1) or OFF (0)
        mvk     .L2     0, b4
        FARCALL HILITE
        mvk     .L1     0, a4
        FARCALL DRAW_ARROWS
        mvk     .L1     0, a4
        mvkl    .S2     STR_BLANK, b4
        mvkh    .S2     STR_BLANK, b4
        mvk     .L1     0, a6
        FARCALL SOFTKEY
        mvk     .L1     1, a4
        mvkl    .S2     STR_EXIT, b4
        mvkh    .S2     STR_EXIT, b4
        mvk     .L1     0, a6
        FARCALL SOFTKEY
        mvk     .L1     2, a4
        mvkl    .S2     STR_BLANK, b4
        mvkh    .S2     STR_BLANK, b4
        mvk     .L1     0, a6
        FARCALL SOFTKEY
        ldw     .D2T1   *+b15(8), a10
        ldw     .D2T1   *+b15(12), a11
        addk    .S2     16, b15
        JUMP    DRAW_DONE

; Stock pack (A4 = 24-byte record, B4 = settings words) then our OFF bits
; into bits 1-4 of byte 23. B3 = return into the stock save.
pack_hook:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(8)
        stw     .D2T1   a4, *+b15(12)
        FARCALL PACK
        ldw     .D2T1   *+b15(12), a4
        mvkl    .S1     MIDI_FLAGS, a0
        mvkh    .S1     MIDI_FLAGS, a0
        ldw     .D1T1   *a0, a0
        nop     3
        ldbu    .D1T1   *+a4(23), a1
        and     .L1     15, a0, a0
        shl     .S1     a0, 1, a0
        nop     2
        or      .L1     a0, a1, a1
        stb     .D1T1   a1, *+a4(23)
        ldw     .D2T2   *+b15(8), b3
        addk    .S2     16, b15
        nop     3
        b       .S2     b3
        nop     5

; Stock unpack at boot (A4 = settings words, B4 = record) then our OFF bits
; from byte 23.
unpack_hook:
        addk    .S2     -16, b15
        stw     .D2T2   b3, *+b15(8)
        stw     .D2T2   b4, *+b15(12)
        FARCALL UNPACK
        ldw     .D2T2   *+b15(12), b4
        nop     4
        ldbu    .D2T2   *+b4(23), b0
        mvkl    .S1     MIDI_FLAGS, a0
        mvkh    .S1     MIDI_FLAGS, a0
        nop     2
        shru    .S2     b0, 1, b0
        and     .L2     15, b0, b0
        stw     .D1T2   b0, *a0
        ldw     .D2T2   *+b15(8), b3
        addk    .S2     16, b15
        nop     3
        b       .S2     b3
        nop     5

; In front of Task_MIDI's CC and PC calls of midi_channel_msg(type, channel,
; number, value): A4 = 0 for CC, 1 for PC; B3 = return into Task_MIDI.
midi_gate:
        mvkl    .S1     MIDI_FLAGS, a0
        mvkh    .S1     MIDI_FLAGS, a0
        ldw     .D1T1   *a0, a0
        mv      .L1     a4, a2              ; a2 = 1 for PC
        mvk     .L1     OFF_CC, a1
  [a2]  mvk     .L1     OFF_PC, a1
        nop     2
        and     .L1     a1, a0, a0
  [a0]  b       .S2     b3                  ; receive off: drop it
        nop     5
        mvkl    .S2     CC_HANDLER, b0
        mvkh    .S2     CC_HANDLER, b0
  [a2]  mvkl    .S2     STOCK_CHANNEL_MSG, b0
  [a2]  mvkh    .S2     STOCK_CHANNEL_MSG, b0
        b       .S2     b0
        nop     5
