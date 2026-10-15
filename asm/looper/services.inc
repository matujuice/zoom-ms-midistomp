; Looper services block (v2.0 step 2), MS-50G 3.10 OS. Layout and rules:
; docs/looper-services.md. The Looper ZDL reads and writes it with plain loads
; and stores; nothing calls into the firmware.
        .equ    SV, 0xC00F3000              ; RAM test region 1, after the MOD code
        .equ    S_MAGIC, 0                  ; 0x5A4C5301 ("ZLS", version 1)
        .equ    S_NREG, 4                   ; big buffer regions (3)
        .equ    S_REG, 8                    ; base, bytes; base, bytes; base, bytes
        .equ    S_CLAIM, 32                 ; ZDL: its params pointer (ctx[1]), 0 = free
        .equ    S_HB, 36                    ; ZDL: +1 every audio block
        .equ    S_SLOT, 40                  ; firmware: the claimant's slot 0-5, -1 = none
        .equ    S_PRESS, 44                 ; firmware: +1 per footswitch / CC press
        .equ    S_MINE, 48                  ; firmware: 1 = the looper is under the cursor (play mode)
        .equ    S_LEDON, 52                 ; firmware: GPIO register that lights the LED
        .equ    S_LEDOFF, 56                ; firmware: GPIO register that darkens it
        .equ    S_LEDMASK, 60               ; firmware: the LED's bit in both
        .equ    S_LEVEL, 64                 ; ZDL: pulse level 0..32 (LED duty and box fill)
        .equ    S_TEXT, 68                  ; ZDL: 8 status characters, space padded
        .equ    S_LASTHB, 96                ; firmware private: heartbeat seen last poll
        .equ    S_STALE, 100                ; firmware private: polls without a heartbeat
        .equ    S_WASMINE, 104              ; firmware private: S_MINE last poll

        .equ    STALE_POLLS, 3              ; 16 ms polls: free the claim after ~48 ms
        .equ    SLOT_STATE, 0x11F03004      ; word 1 of slot 0's state block = its params pointer
        .equ    SLOT_STRIDE, 212
        .equ    GPIO_BANK01, 0x1181DE70     ; pointer the OS's GPIO writer uses (pin 0 = LED)
        .equ    LED_APPLIED, 0xC00EF078     ; bit 0: LED state the LED task wrote last
        .equ    CURSOR, 0xC009C064          ; signed byte: cursor of view 0
        .equ    CURSOR_SLOT, 0xC00EEEB0     ; word [24 x cursor]: slot under it (view 0)
        .equ    MODE, 328                   ; B14 offset, 0 = play
