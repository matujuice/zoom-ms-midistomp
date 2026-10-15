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

; MIDISTOMP layout that differs per build
        .equ    CC_HANDLER, 0x1181DEA0      ; asm/midi_cc/handler.S (L2)
