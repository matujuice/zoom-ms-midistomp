# Looper services block (v2.0 step 2)

From MIDISTOMP v2.0 the firmware gives the Looper ZDL (effects pack, fxid 497)
a big buffer, counts footswitch and CC presses for it, and lets it drive the
LED. Everything goes through one block in RAM; the ZDL uses plain loads and
stores and never calls into the firmware. MS-50G 3.10 OS only.
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
| 16 | 64 | ZDL | pulse level 0..32 (LED duty, status box fill) |
| 17, 18 | 68 | ZDL | 8 status characters, space padded |
| 24-26 | 96 | firmware | private (last heartbeat, polls without one, "was under the cursor") |
| 27-29 | 108 | firmware | private (status text and fill step last drawn) |
| 31 | 124 | boot | end mark `0x5A4C53FF` |

Big buffer (RAM test, issue #19; nothing in the OS writes there):

| Region | Base | Bytes |
|---|---|---|
| 3 | `0xC0636980` | 1,677,952 |
| 2 | `0xC01ADAD4` | 337,196 |
| 1 | `0xC0102000` | 614,400 (region 1 above the 64 KB kept for MOD code) |

With the looper's own 705 KB slot block that is 3.3 MB: 24.7 s stereo or
48.4 s mono in 12-bit block float.

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
  bit (`0xC00EF078` bit 0) so it writes the new effect's state again.
- **Screen:** while word 12 is 1 and no overlay or prompt is open, every
  screen draw adds a status box top right of the Effect View (x 79-127,
  y 0-9, above the knob frame at y 11): the 8 characters of words 17-18 in the
  OS font on a dither fill set by word 16 (0-3 none, 4-11 25 %, 12-19 50 %,
  20-27 75 %, 28-32 full). From 75 % the text is white with a black 1-pixel
  edge, below it black with a white edge. The 16 ms poll asks the UI for a
  redraw (event 0x40) when the text or the fill step changes.
- **Never** change the address, magic or word layout without a new magic
  (version byte).
