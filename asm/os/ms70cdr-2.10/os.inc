; MS-70CDR 2.10 OS addresses used by the MIDISTOMP sources: the same names as
; ../ms50g-3.10/os.inc. Each was matched to the MS-50G one in the 70CDR
; disassembly (same code, shifted addresses): docs/ms70cdr-port.md,
; "Port to the MS-70CDR OS".

; Functions
        .equ    MIDI_CHANNEL_MSG, 0xC00ADF20 ; (type, channel, number, value)
        .equ    FX_PARAM_DESC, 0xC00B056C   ; (slot, param) -> descriptor, max at +12
        .equ    FX_SET_PARAM, 0xC00BB600
        .equ    SEM_PEND, 0xC00C7EE0
        .equ    SEM_POST, 0xC00D6B00
        .equ    UI_REFRESH, 0xC00ACD84
        .equ    EVENT_POST, 0xC00CBF40
        .equ    DIVU, 0xC00DC560            ; a4 = a4 / b4 (unsigned), RTS
        .equ    CLOCK_GETTICKS, 0xC00DEE20  ; SYS/BIOS Clock_getTicks, 1 ms
        .equ    SET_SETTING, 0xC00CAB44     ; (setting, value, notify)
; Data
        .equ    TEMPO_VALUE, 0xC009C06C     ; patch TEMPO, int BPM (same address)
        .equ    TEMPO_SETTING, 0xC00EDEE0   ; value ptr, min 40, max 250
; B14 offsets (B14 = 0xC00EF748 here, 0xC00EFCC0 on the 50G)
        .equ    SEM_HANDLE_OFS, 764         ; effect semaphore
        .equ    UI_EVENT_OFS, 656           ; UI task event
        .equ    CUR_PATCH, 324              ; current patch 0-49
        .equ    MIDI_RD_OFS, 216            ; Task_MIDI receive ring read index
        .equ    MIDI_BYTE_OFS, 226          ; Task_MIDI: the byte just taken

; UI: menus and lists (midi-settings)
        .equ    SET_SCREEN, 0xC00A75E0      ; (screen, row)
        .equ    LIST_INDEX, 0xC00A7040      ; -> row + top of the list
        .equ    LIST_SCROLL, 0xC00A72D4     ; (delta, rows)
        .equ    STOCK_MENU_KEYS, 0xC00A79B4
        .equ    STOCK_LIST_KEYS, 0xC00A7904
        .equ    KEY_DONE, 0xC00A83C0        ; key dispatcher epilogue, A4 = redraw
        .equ    DRAW_DONE, 0xC00A9404       ; draw dispatcher epilogue
        .equ    DRAW_TITLE, 0xC00A7378      ; (string)
        .equ    DRAW_TEXT, 0xC009FCE0       ; (0, string, x, y)
        .equ    DRAW_ICON, 0xC009F9B0       ; (0, x, y, w, h, bitmap)
        .equ    DRAW_BOX, 0xC00A0144        ; (0, x, y, x2, y2, mode)
        .equ    HILITE, 0xC00A73A4          ; (row, narrow for a scrollbar)
        .equ    SCROLLBAR, 0xC00A8874       ; (top, rows)
        .equ    DRAW_ARROWS, 0xC00A7400     ; (0)
        .equ    SOFTKEY, 0xC009F8F0         ; (knob, string, 0)
        .equ    CLAMP, 0xC00A766C           ; (value, min, max)
        .equ    BATTERY_LEVEL, 0xC00D7260   ; -> 0..4, 5+ = no battery icon
        .equ    BATTERY_ICONS, 0xC00EEA50
        .equ    SAVE_SETTINGS, 0xC00BA3E4   ; (words), writes record 50
        .equ    PACK, 0xC00D382C            ; (24-byte record, 38 words), same bit widths
        .equ    UNPACK, 0xC00D3740
        .equ    REC_SAVE, 0xC00B49F4        ; (record, buffer)
        .equ    REC_LOAD, 0xC00B4AAC        ; (record, buffer) -> 0 = ok
        .equ    SAVE_LAST_PATCH, 0xC00B8410 ; (patch), writes record 51
        .equ    SETTINGS_WORDS, 0xC009D8F8  ; stock settings, 38 words
        .equ    HOLD_WORD, 0xC009D920       ; stock HOLD FOR: 0 tuner, 1 tempo
        .equ    LIST_ROW_OFS, 356           ; B14: highlighted screen row
        .equ    LIST_TOP_OFS, 360           ; B14: list index of the top row
; Strings
        .equ    STR_MENU, 0xC00E90F1
        .equ    STR_SETTINGS, 0xC00E9004
        .equ    STR_ENTER, 0xC00E90F6
        .equ    STR_EXIT, 0xC00E90FC
        .equ    STR_BLANK, 0xC00E9101
        .equ    STR_DELETE_UNIT, 0xC00E8FE4 ; menu entries
        .equ    STR_CHAIN, 0xC00E8FF7
        .equ    STR_VERSION, 0xC00E900D     ; version-1.1 makes it V1.1
        .equ    STR_SET1, 0xC00E9028        ; SETTINGS rows 1-6 (BYPASS/MUTE TUNER ...
        .equ    STR_SET2, 0xC00E903A
        .equ    STR_SET3, 0xC00E904B
        .equ    STR_SET4, 0xC00E9055
        .equ    STR_SET5, 0xC00E9062
        .equ    STR_SET6, 0xC00E9070        ; ... LCD CONTRAST)
        .equ    STR_TUNER, 0xC00E909F
        .equ    STR_TEMPO, 0xC00EB0DC       ; the tempo box title
        .equ    OFF_ON, 0xC00ECD38          ; "OFF", "ON"
; Keys, footswitch, tempo screen (tempo-hold)
        .equ    OVL_GET, 0xC00CCD6C         ; (0) -> overlay state, -1 = none
        .equ    OVL_SET, 0xC00CCC84         ; (0, state, ms)
        .equ    TEMPO_BOX, 0xC00AAB10       ; (0, tempo)
        .equ    TOGGLE, 0xC00ABCB8          ; (slot)
        .equ    IS_DIRTY, 0xC00B8534
        .equ    STOCK_KNOB, 0xC00AC0E8
        .equ    STOCK_TAP, 0xC00BA488
        .equ    STOCK_HOLD, 0xC00ABD30
        .equ    STOCK_RELEASE, 0xC00AC8FC
        .equ    STOCK_TYPE_HOLD, 0xC00ABA58
        .equ    STOCK_CURSOR_HOLD, 0xC00AB968
        .equ    STOCK_TYPE_REL, 0xC00AC450
        .equ    STOCK_CURSOR_REL, 0xC00AC30C
        .equ    STOCK_MIDDLE, 0xC00AC790    ; event 65
        .equ    FOOT_PRESS, 0xC00AC990      ; event 32
        .equ    SW_STATE, 0xC009DF90        ; 7 switches, bit i clear = down
        .equ    MODE, 320                   ; B14: 0 = play, 5/6 = tuner, 11 = menu
        .equ    PENDING, 340                ; B14: stock keys cancel it first
        .equ    HOLD_FIRED, 348             ; B14: 1 = the release does not tap
; Effect scrolling (scroll)
        .equ    STOCK_STEP, 0xC00C4AE4      ; step(A4 = dir +1 / -1)
        .equ    STOCK_SLEEP, 0xC00CEBC0     ; sleep(A4 = ms)
        .equ    STOCK_BUMP, 0xC00C4C4C      ; bump(A4 = dir)
        .equ    CURSOR, 0xC009C064          ; byte 0 = cursor (5 = effect 1), word 1 = effect count

; MIDISTOMP layout that differs per build
        .equ    CC_HANDLER, 0xC00F2800      ; handler.S in DDR: the OS uses L2 up to 0x1181DF04
        .equ    TUNER_LABEL_TRAMP, 0xC00DFA50 ; asm/tempo_hold/tuner_label_trampoline.S
