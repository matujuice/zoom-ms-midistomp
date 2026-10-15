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

; MIDISTOMP layout that differs per build
        .equ    CC_HANDLER, 0xC00F2800      ; handler.S in DDR: the OS uses L2 up to 0x1181DF04
