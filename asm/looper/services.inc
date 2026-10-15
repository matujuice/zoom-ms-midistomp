; Looper services block (v2.0 step 2), MS-50G 3.10 and MS-70CDR 2.10 OS (the same). Layout and rules:
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
        .equ    S_LEVEL, 64                 ; ZDL: LED level 0..32 (its own PWM)
        .equ    S_TEXT, 68                  ; ZDL: 8 status characters, space padded
        .equ    S_PROG, 76                  ; ZDL: loop progress 0..256 (box fill)
        .equ    S_INV, 80                   ; ZDL: 1 = box inverted (pulse, blink)
        .equ    S_LASTHB, 96                ; firmware private: heartbeat seen last poll
        .equ    S_STALE, 100                ; firmware private: polls without a heartbeat
        .equ    S_WASMINE, 104              ; firmware private: S_MINE last poll
        .equ    S_DTEXT, 108                ; firmware private: status text last drawn (8 bytes)
        .equ    S_DKEY, 116                 ; firmware private: progress / 4 + inverted x 256 last drawn

        .equ    STALE_POLLS, 3              ; 16 ms polls: free the claim after ~48 ms

; The OS addresses the hooks use (slot state blocks, LED, cursor, screen) are
; in asm/os/<build>/os.inc, "Looper services".
