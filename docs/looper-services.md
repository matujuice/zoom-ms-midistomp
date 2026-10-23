# Looper services block (v2.0 step 2)

From MIDISTOMP v2.0 the firmware gives the Looper ZDL (effects pack, fxid 497)
a big buffer, counts footswitch and CC presses for it, and lets it drive the
LED. Everything goes through one block in RAM; the ZDL uses plain loads and
stores and never calls into the firmware. MS-70CDR 2.10 OS (every pedal runs it from v2.0).
The transport block (`docs/transport-block.md`) is separate and unchanged.

## Where

Address **`0xC00F3000`** (DDR, RAM test region 1, inside the 64 KB kept for MOD
code), 128 bytes, loaded at boot.

| word | offset | written by | meaning |
|---|---|---|---|
| 0 | 0 | boot | magic + version **`0x5A4C5301`** ("ZLS", version 1). Anything else: no services |
| 1 | 4 | boot | big buffer regions: 3 |
| 2-7 | 8 | boot | base, bytes of each region (below) |
| 8 | 32 | ZDL | claim: the params pointer (`ctx[1]`) of the looper using the services, 0 = free |
| 9 | 36 | ZDL | heartbeat: +1 every audio block while it holds the claim |
| 10 | 40 | firmware | the claimant's slot 0-5, -1 = none |
| 11 | 44 | firmware | press counter |
| 12 | 48 | firmware | 1 = the looper is under the cursor in play mode: the ZDL drives the LED |
| 13 | 52 | firmware | GPIO register that lights the LED (write the mask) |
| 14 | 56 | firmware | GPIO register that darkens it |
| 15 | 60 | firmware | the LED's bit |
| 16 | 64 | ZDL | LED level 0..32 (its own PWM) |
| 17, 18 | 68 | ZDL | 8 status characters, space padded |
| 19 | 76 | ZDL | bits 0-15 box fill 0..256 (blink applied); 16-21 cycle C in bars; 22-27 bar 1..32 in the cycle; 28-29 beat - 1; 30 = no clock ("NO CLK"). Older ZDLs write the fill only (C = 0: no bar lines, no right text) |
| 20 | 80 | ZDL | 1 = status box inverted (pulse, blink); GRDLOOP writes 0 and the new bar ignores it |
| 21 | 84 | Perform | the patch's Perform CYCLE in bars (1-32), 0 = none: the looper's Cycle knob is used. Zero at boot; Perform mode will write it (not built yet) |
| 24-26 | 96 | firmware | private (last heartbeat, polls without one, "was under the cursor") |
| 27-29 | 108 | firmware | private (status text, progress / 4 + inverted x 256 last drawn) |
| 30 | 120 | ZDL | left text as a code (the firmware spells it): bits 0-3 kind (0 = an older ZDL, use words 17-18; 1 EMPTY, 2 REC IN, 3 STOP IN, 4 PLAY IN, 5 REC n, 6 REC n/m, 7 PLAY n BARS, 8 STOPPED), 4-9 n, 10-15 m, 16 = n in beats (else bars), 17 = MONO |
| 31 | 124 | boot | end mark `0x5A4C53FF` |

Big buffer (RAM test, issue #19; nothing in the OS writes there):

| Region | Base | Bytes |
|---|---|---|
| 3 | `0xC0636980` | 1,677,952 |
| 2 | `0xC0198000` | 425,984 |
| 1 | `0xC0116000` | 532,480 (region 1 above the 96 KB kept for MOD code and record 50, and 48 KB for MASTER) |

With the looper's own 705 KB slot block that is about 3.4 MB: 25.4 s stereo
or 49.7 s mono in 12-bit block float. The regions were confirmed free on the
70CDR OS by the RAM test (2026-10-15).

## Rules

- **Claim:** a looper takes the block only while the claim is 0 and it has no
  loop of its own in its slot block. The firmware's 16 ms poll frees a claim
  whose heartbeat has not moved for 3 polls (deleted, unloaded, patch change
  with no looper). So one looper per patch gets the services; a second one
  keeps its slot block and counts on/off flips.
- **Slot:** the poll finds the claimant's slot as the slot state block
  (`0x11F03000 + 212 x slot`) whose word 1 equals the claim (the same pointer
  the effect gets as `ctx[1]`, found by TempoPrb). Until it has, the slot
  word is -1 and the footswitch flips the looper as before, so the ZDL counts
  flips while the slot word is -1.
- **Presses:** the firmware adds 1 (interrupts off) when the footswitch is
  pressed with the looper's slot under the cursor (instead of flipping it),
  and when the looper slot's on/off CC (10n+4) arrives with a value of 64-127
  (0-63 is dropped). The ZDL acts on the difference since the last block. A
  footswitch hold does nothing while the looper is under the cursor.
- **LED:** pin 0 of GPIO bank 0, active low (inferred from the LED task,
  which writes 1 - "lit"). While word 12 is 1 the ZDL switches it every block
  (PWM); the LED task only writes on a change, so it stays out of the way.
  When the cursor leaves the looper the poll flips the LED task's "written"
  bit (`0xC00EEB10` bit 0) so it writes the new effect's state again.
- **Screen:** while word 12 is 1 and no overlay or prompt is open, every
  screen draw adds a status bar to the Looper's Effect View, drawn like Perform
  mode's top bar (`asm/looper/lbox.c`, `docs/perform-ui-mockup.html`): knob
  pages: none since PERFORM11; cover x 0-127,
  y 17-34, exactly where the GRDLOOP cover's bar is. Filled black from the left
  by word 19, the word 30 text left and bar.beat/C right in FONT7 (proportional,
  inverted over the fill), a gap in the edge and a dotted line at each bar line.
  The 16 ms poll asks the UI for a redraw (event 0x40) when the text, the
  progress (in 64ths) or word 20 changes; the bar/beat bits change every beat,
  so a new word 30 shows within one beat.
- **Never** change the address, magic or word layout without a new magic
  (version byte).
