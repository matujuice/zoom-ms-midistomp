; MS-50G 3.10 OS addresses used by the MIDISTOMP sources (`.include "os.inc"`;
; zoomms/asm.py picks this file with -I asm/os/<build id>).
; Where they come from: docs/os-reverse-engineering.md. The MS-70CDR 2.10
; values are in ../ms70cdr-2.10/os.inc (docs/ms70cdr-port.md).

; Functions
        .equ    MIDI_CHANNEL_MSG, 0xC00AE0F8 ; (type, channel, number, value)
        .equ    FX_PARAM_DESC, 0xC00B07AC   ; (slot, param) -> descriptor, max at +12
        .equ    FX_SET_PARAM, 0xC00BAEE0
        .equ    SEM_PEND, 0xC00C7C60
        .equ    SEM_POST, 0xC00D70C0
        .equ    UI_REFRESH, 0xC00ACEA4
        .equ    EVENT_POST, 0xC00CC680
        .equ    DIVU, 0xC00DCA20            ; a4 = a4 / b4 (unsigned), RTS
        .equ    CLOCK_GETTICKS, 0xC00DF360  ; SYS/BIOS Clock_getTicks, 1 ms
        .equ    SET_SETTING, 0xC00CAC64     ; (setting, value, notify)
; Data
        .equ    TEMPO_VALUE, 0xC009C06C     ; patch TEMPO, int BPM
        .equ    TEMPO_SETTING, 0xC00EE3D8   ; value ptr, min 40, max 250
; B14 offsets
        .equ    SEM_HANDLE_OFS, 784         ; effect semaphore
        .equ    UI_EVENT_OFS, 676           ; UI task event
        .equ    CUR_PATCH, 332              ; current patch 0-49
        .equ    MIDI_RD_OFS, 224            ; Task_MIDI receive ring read index
        .equ    MIDI_BYTE_OFS, 234          ; Task_MIDI: the byte just taken

; UI: menus and lists (midi-settings)
        .equ    SET_SCREEN, 0xC00A75E0      ; (screen, row)
        .equ    LIST_INDEX, 0xC00A7040      ; -> row + top of the list
        .equ    LIST_SCROLL, 0xC00A72D4     ; (delta, rows)
        .equ    STOCK_MENU_KEYS, 0xC00A79B4
        .equ    STOCK_LIST_KEYS, 0xC00A7904
        .equ    KEY_DONE, 0xC00A840C        ; key dispatcher epilogue, A4 = redraw
        .equ    DRAW_DONE, 0xC00A9468       ; draw dispatcher epilogue
        .equ    DRAW_TITLE, 0xC00A7378      ; (string)
        .equ    DRAW_TEXT, 0xC009FCE0       ; (0, string, x, y)
        .equ    DRAW_ICON, 0xC009F9B0       ; (0, x, y, w, h, bitmap)
        .equ    DRAW_BOX, 0xC00A0144        ; (0, x, y, x2, y2, mode)
        .equ    HILITE, 0xC00A73A4          ; (row, narrow for a scrollbar)
        .equ    SCROLLBAR, 0xC00A88CC       ; (top, rows)
        .equ    DRAW_ARROWS, 0xC00A7400     ; (0)
        .equ    SOFTKEY, 0xC009F8F0         ; (knob, string, 0)
        .equ    CLAMP, 0xC00A766C           ; (value, min, max)
        .equ    BATTERY_LEVEL, 0xC00D7820   ; -> 0..4, 5+ = no battery icon
        .equ    BATTERY_ICONS, 0xC00EEFB8
        .equ    SAVE_SETTINGS, 0xC00B9D04   ; (words), writes record 50
        .equ    PACK, 0xC00D3C6C            ; (24-byte record, 38 words), same bit widths
        .equ    UNPACK, 0xC00D3B80
        .equ    REC_SAVE, 0xC00B4C94        ; (record, buffer)
        .equ    REC_LOAD, 0xC00B4D4C        ; (record, buffer) -> 0 = ok
        .equ    SAVE_LAST_PATCH, 0xC00B86D0 ; (patch), writes record 51
        .equ    SETTINGS_WORDS, 0xC009D8F8  ; stock settings, 38 words
        .equ    HOLD_WORD, 0xC009D920       ; stock HOLD FOR: 0 tuner, 1 tempo
        .equ    LIST_ROW_OFS, 368           ; B14: highlighted screen row
        .equ    LIST_TOP_OFS, 372           ; B14: list index of the top row
; Strings
        .equ    STR_MENU, 0xC00E958C
        .equ    STR_SETTINGS, 0xC00E94A4
        .equ    STR_ENTER, 0xC00E9591
        .equ    STR_EXIT, 0xC00E9597
        .equ    STR_BLANK, 0xC00E959C
        .equ    STR_DELETE_UNIT, 0xC00E9484 ; menu entries
        .equ    STR_CHAIN, 0xC00E9497
        .equ    STR_VERSION, 0xC00E94AD     ; version-1.1 makes it V1.1
        .equ    STR_SET1, 0xC00E94C8        ; SETTINGS rows 1-6 (BYPASS/MUTE TUNER ...
        .equ    STR_SET2, 0xC00E94DA
        .equ    STR_SET3, 0xC00E94EB
        .equ    STR_SET4, 0xC00E94F5
        .equ    STR_SET5, 0xC00E9502
        .equ    STR_SET6, 0xC00E9510        ; ... LCD CONTRAST)
        .equ    STR_TUNER, 0xC00E953F
        .equ    STR_TEMPO, 0xC00EB13F       ; the tempo box title
        .equ    OFF_ON, 0xC00ED238          ; "OFF", "ON"
; Keys, footswitch, tempo screen (tempo-hold)
        .equ    OVL_GET, 0xC00CBA10         ; (0) -> overlay state, -1 = none
        .equ    OVL_SET, 0xC00CB8A4         ; (0, state, ms)
        .equ    TEMPO_BOX, 0xC00AAC48       ; (0, tempo)
        .equ    TOGGLE, 0xC00ABDE4          ; (slot)
        .equ    IS_DIRTY, 0xC00B87F4
        .equ    STOCK_KNOB, 0xC00AC214
        .equ    STOCK_TAP, 0xC00B9DA8
        .equ    STOCK_HOLD, 0xC00ABE58
        .equ    STOCK_RELEASE, 0xC00ACA1C
        .equ    STOCK_TYPE_HOLD, 0xC00ABB80
        .equ    STOCK_CURSOR_HOLD, 0xC00ABA90
        .equ    STOCK_TYPE_REL, 0xC00AC574
        .equ    STOCK_CURSOR_REL, 0xC00AC434
        .equ    STOCK_MIDDLE, 0xC00AC8B0    ; event 65
        .equ    FOOT_PRESS, 0xC00ACAB0      ; event 32
        .equ    SW_STATE, 0xC009DF90        ; 7 switches, bit i clear = down
        .equ    MODE, 328                   ; B14: 0 = play, 5/6 = tuner, 11 = menu
        .equ    PENDING, 348                ; B14: stock keys cancel it first
        .equ    HOLD_FIRED, 360             ; B14: 1 = the release does not tap
; Effect scrolling (scroll)
        .equ    STOCK_STEP, 0xC00C4C64      ; step(A4 = dir +1 / -1)
        .equ    STOCK_SLEEP, 0xC00CF000     ; sleep(A4 = ms)
        .equ    STOCK_BUMP, 0xC00C4DCC      ; bump(A4 = dir)
        .equ    CURSOR, 0xC009C064          ; byte 0 = cursor (5 = effect 1), word 1 = effect count

; MIDISTOMP layout that differs per build
        .equ    CC_HANDLER, 0x1181DEA0      ; asm/midi_cc/handler.S (L2)
        .equ    CC_TRAMP, 0xC00AF408       ; asm/midi_cc/trampoline.S (midi_gate jumps here)
        .equ    TUNER_LABEL_TRAMP, 0xC00DAFD0 ; asm/tempo_hold/tuner_label_trampoline.S
