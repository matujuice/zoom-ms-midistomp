# Mixer Mode M3 research: the stock Effect Chain screen (MS-70CDR 2.10, 2026-10-18)

Static disassembly by a research agent; screen-3 key entry and the swap function start re-checked
by the main session. Nothing here is pedal-verified.

All addresses are MS-70CDR 2.10 (TI dis6x, 32-byte aligned starts, plus table decoding). B14
offsets use the 70CDR values (MODE 320, SCREEN 352).

A "switch-table entry" is a 32-bit pointer to a 3-instruction stub (`callp handler; lddw
*+B15[1],A5:A4; bnop epilogue`), not a callp word. Screen id = (entry - table base) / 4 + 1.

## 1. Which screen is the stock Effect Chain screen

| what | address | conf | evidence |
|---|---|---|---|
| Screen id | **3**, MODE 11 (menu), from menu row 1 "EFFECT CHAIN" | high | Menu ENTER jump table `0xC00EF2F4`: row 0 -> `0xC00A7A0C` SET_SCREEN(2,0); **row 1 -> `0xC00A7A16` SET_SCREEN(3,0), then `callp 0xC00B6D84`**; row 2 -> screen 1; row 3 -> screen 9 |
| Entry side effect | `0xC00B6D84` sets the row to count-1 (`0xC00B6BA0` = effect count, `0xC00A72CC` = store row) | high | Entering starts on the rightmost effect (slot 0) |
| Key table | base **`0xC00EEFA0`** (id 1); id 3 entry **`0xC00EEFA8`** -> stub `0xC00A83A0` -> `callp 0xC00B7618` | high | Dispatcher `0xC00A82AC`: `B14[88]-1 <= 16` indexes the table |
| Draw table | base **`0xC00EEBB4`** (id 1); id 3 entry **`0xC00EEBBC`** -> stub `0xC00A93F0` -> `callp 0xC00B71CC` (epilogue `0xC00A9404`) | high | Same method |
| Key handler `0xC00B7618` (A4 = event, A5 = steps; A4 = 1 redraw) | **34 (knob 1 press):** `B14[151]` (604) = 1 - `B14[151]`, then lift anim `0xC00B74F4` if lifted, else drop anim `0xC00B7428`. **65 (knob 2):** if lifted, clear `B14[151]` and drop; then always `SET_SCREEN(0,1)`. **160 (knob 1 turn):** sign(steps) -> row clamped to 0..count-1 (`0xC00A766C`), stored with `0xC00A72CC`; if changed: slide `0xC00B6DC0(dir)`, and **only if lifted** swap `0xC00B6BC4(oldRow, newRow)`. Other events return 0 | high | 0xB7618-0xB76F4 |
| Draw handler `0xC00B71CC` | `DRAW_TITLE("EFFECT CHAIN" @0xC00EC4BC)`; the crane hook glyph; three covers; hint arrows `0xC00A83C8(0)`; softkeys via `0xC009F8F0`: knob 0 "LIFT UP" (`0xC00EC4C9`) / "LIFT DWN" (`0xC00EC4D1`) by `B14[151]`, knob 1 "EXIT" (`0xC00EC4DA`), knob 2 blank | high | Strings present |
| State | `B14[89]` (356) row; `B14[151]` (604) lifted; `B14[150]` (600) bit 0 busy during a swap; `B14[98]` (392) = 1 while a swap/apply runs; `B14[188]` (752) semaphore of the animations (pend `0xC00C7EE0`, post `0xC00D6B00`); `B14[191]` (764) effect semaphore (swap, delete, change type) | medium for 150/98/188/191 | Usage only; 50G +784 / +772 |
| Row to slot | **slot = count-1-row** (`0xC00B6BAC`) | high | Row 0 = leftmost cover = last effect |
| Other screens in the tables | key: 1 `0xA7904` list, 2 `0xA8238` (DELETE EFFECT UNIT confirm), 4-8, 12 settings, 9 `0xA7628` VERSION, 10 `0xA7778`, 16 `0xA7CB8`, 17 `0xA77C8`; ids 11, 13, 14, 15 = default stub `0xA8310` (15 = MIXER). 32 -> `0xA7A6C`, 34 -> `0xA768C` (compare chain); 33 also `0xA7A6C` | high | Dispatcher 0xA82AC |

## 2. Draw path

| primitive | signature | conf |
|---|---|---|
| `0xC009F9B0` blit + mark dirty | (frame A4, x B4, y A6, w B6, h A8, src B8); calls `0xC009DFC0` (blit into FB `0x11816800 + frame*1024`), sets FB_DIRTY (`0xC00EEBB0+frame`) | high |
| `0xC00A0144` rect/line | (frame, x1 B4, y1 A6, x2 B6, y2 A8, mode B8); modes 0-4 from `0xC009E9F4` lines; mode 2 for the cursor box and band clears | medium |
| `0xC00A13D4` capture | (frame A4, buf B4, x1 A6, y1 B6, x2 A8, y2 B8): FB rectangle -> RAM | medium |
| `0xC00A9B18` bold 7-px text | (frame, string, x, y) | medium |
| `0xC009FCE0` text, `0xC009F8F0` softkey, `0xC00A7378` title | as in mixer.S | high |
| `0xC00B6D94` refresh | pends the LCD lock, LCD send `0xC00B57C8`, releases | medium |
| `0xC00CEBC0(ms)` | sleep (100 / 150) | medium |

| what | address | conf | evidence |
|---|---|---|---|
| **One cover** | `0xC00A89B4(name A4, x B4, y A6, nchars B6 = 5, on A8)`: blits the 38 x 23 box, **ON `0xC00EB4E8`, OFF/dotted `0xC00EB560`**; name in 2 lines of 5 with `0xC00A9B18` at x+19, y+4 and y+12 | high | Callers: screen-3 draw (`0xB7278`, `0xB72F4`, `0xB730C`, `0xB7394`), settings helper `0xA8B34` |
| Cover width | **38 px, not 33** (brief). Covers at x = **3, 45, 87** (pitch 42, gap 4), y = 25 (y = 10 lifted). Cursor rect `0xC00A0144(0,45,25,82,49, mode 2)` | high (code) | Check a photo before copying the geometry |
| Dotted rule | on = 0 when the effect is OFF **or** its bit is set in the DSP-off mask `0xC009C060` | high | `0xB7230`-`0xB724C` |
| Name source | `0xC00B71B8(row)` -> `0xC00B056C(slot,1)` | medium | |
| Jack icons | **OUT plug 38x24 `0xC00EAEA0`** at (3,25) left of row 0; **IN plug 38x24 `0xC00EAE08`** at (87,25) right of the last, via `0xC009F9B0` (`0xB7284`, `0xB73A8`); only when no effect is on that side | high | Both dumped |
| Slide halves | 19x24 pieces at x = 0 / 108, y = 25: plug `0xC00EBB50` / `0xC00EBB00`, ON cover `0xC00EBE68` / `0xC00EBE28`, OFF cover `0xC00EBEE8` / `0xC00EBEA8` | medium | Used by `0xB6DC0` |
| Crane hook | 12x12 at (58,10): `0xC00EC8F8` | high | |
| Turn hint ("◄ ►") | `0xC00A83C8(knob)`: two 3x5 glyphs at y = 51 from `0xC00ED0A0` / `0xC00ED0A8`; x = `0xC00ECC38[knob] - 4` and `+ 1`; screen 3 calls it with knob 0 (`0xB73C4`) | medium | |
| **Side scroll arrows** | **Not found.** The only arrows on screen 3 are the turn hint | n/a | Maybe the play-mode cover view `0xC00AA3D8` (not examined) |
| Crane animation | **lift `0xC00B74F4`**: pends B14[188], redraws the hook (10 -> 14), captures the middle column into `0xC00998B8` / `0xC0099CB8`, redraws it shifted up, refreshes, sleeps 100, 100, 150, 150 ms. **drop `0xC00B7428`**: reverse, 100, 100, 150 | medium | |
| Slide `0xC00B6DC0(dir)` | captures covers into `0xC009A0B8` / `0xC009A2B8`, one half-step frame, refresh, 150 ms, post | medium-low | |

## 3. Key path: cursor, lift, move

| what | address | conf | evidence |
|---|---|---|---|
| Cursor | event 160; the row `B14[89]`, not the play-mode cursor `0xC009C064` | high | |
| Lift / drop | `B14[151]` toggled by event 34; data unchanged until a move | high | |
| **Slot swap** | **`0xC00B6BC4(rowA, rowB)`** at `0xB76A4` when lifted: rows -> slots; takes `B14[191]`; 1) swaps the two 44-byte records of the live patch `0xC009BF58 + 44*slot` (3x memcpy `0xC00DDDA0` via a stack temp); 2) swaps their bits in the DSP-off mask `0xC009C060`; 3) `B14[150] \|= 1`; 4) `0xC00DF724` fades out (`0x11F03B6C`), `B14[98]` = 1; 5) per slot `0xC00D7B4C(state)` = FX_TABLE `0xC00EE930[slot]` := mute `0xC00E0784`, and `0xC00AF2E4(slot, effect id)` reloads the effect; 6) `0xC00B86E4(patch, 0)` apply; 7) `B14[98]` = 0, `0xC00DF700` fades in; 8) `0xC00CB300(slotA, slotB)` swaps the per-slot delay memory in DDR; 9) clears `B14[150]` bit 0, posts | high 1-4, 7-9; medium 5-6 | 0xB6BC4-0xB6D80 |
| `0xC00B86E4` | resets the six slot states (`0xC00D8D90`, tables `0xC009DD90`), copies 264 B to a shadow `0xC009C1A0`, `0xC00C3E00(flag)` restores each slot's audio function (`0xC00D7B20` at `0xC00C3CE0`). Also used by add / delete | medium-low | FX_TABLE restore inferred, not traced to the end |
| Slot states | `0xC00C8E6C(slot)` = `0x11F03000 + 212*slot`; the swap resets them, doesn't swap them | high / medium | |
| Untouched | the patch tail (count `0xC009C068`, cursor `0xC009C064`, tempo, name); the DSP-off mask follows the effects | high | |

For M3: the engine's `LAYOUT[slot]` (bus per slot, `0xC00F6000+128`) must be swapped in the same
place (e.g. a hook near `0xC00B6CF4`, after the record swap), and shifted by add and delete.

## 4. Add / delete / change type / DSP Full

| what | address | conf | evidence |
|---|---|---|---|
| **Add** | Hold cursor ◄/► (events 230 right, 231 left, timers 6/7) -> `STOCK_CURSOR_HOLD 0xC00AB968`: `0xC00C2018` (count < 6) else "MAX EFFECT UNIT!" (`0xC00EBD5F`); then MODE := 11, `0xC00C1FE0(cursorslot, dir)` stores the anchor in `B14[32]`, side in `B14[33]`, `SET_SCREEN(33, 0)`. Screen 33 keys `0xC00A7A6C`; ENTER -> **`0xC00C22F4(effectId)`** inserts: shifts records, `AF2E4`, mask, count+1, `ABACC`. Ids from `0xC00ECAC8[row]` | high entry, medium body | |
| **Delete** | Menu row 0 -> screen 2 -> keys `0xC00A8238` -> **`0xC00C2030`**: fade out, mute all, shift records down (memcpy + `0xC00CB300` per step), `AF2E4`, clear the last slot (id -1 at +4, mask bit), count-1, cursor adjust, `0xC00ABACC(count-2, 0)` | high entry, medium-high body | |
| **Change type** | +/- release (events 69/71, `STOCK_TYPE_REL 0xC00AC450` -> `0xC00AC5C0`) and screens 32/33 ENTER -> **`0xC00ABACC(slot, effectId)`**: pend `B14[191]`, `D2E20`, mute `D7B4C`, reset `D8D90`, `AF2E4`, **`0xC00BB600(slot, 1, id, 1, 1)`** (fx_set_param), restore FX_TABLE (`D7B20`), mask fix-up (`D2DEC`) | high | |
| Hold +/- (228/229) | `STOCK_TYPE_HOLD 0xC00ABA58`: MODE := 11, `SET_SCREEN(32, 0)` = type select | high | |
| Toggle ON/OFF | `0xC00ABCB8(slot)` -> `0xC00BB600(slot, 0, newOn, 1, 1)` | high | |
| **DSP Full** | `0xC00BB4E0(mask)`: sums the cost (float at +0x28 of `0xC00B056C(slot,1)`), **1 when >= 225.0** (`mvkh 0x4361` at `0xC00BB52C`). `0xC00BB544(list, table 0xC00EEA38, preferredMask)` clears slot bits until it fits. Callers: fx_set_param param 1 (`0xC00BB7C4`), the patch validator `0xC00C0848` (`0xC00C08E8` / `0xC00C090C`, from patch load `0xC00B82FC`). Result -> DSP-off mask `0xC009C060` | high | Confirms mixer-mode-m0.md section 2 |
| Gap | the ON toggle doesn't call `BB4E0`/`BB544`; the "DSP FULL" text/bitmap not found | medium | |

## 5. Effect View knob pages: tab row

| what | address | conf | evidence |
|---|---|---|---|
| Play-mode draw | `0xC00BA9D8..BAA52`: slot from CURSOR_SLOT `0xC00EE748`; `VIEW_KNOBS[view]` (`0xC009D398`) != 0 -> **`0xC00CAFA0(view, slot)`** (knob pages) else `0xC00AA3D8(view, slot)` (covers); call at `0xC00BAA4C` | high | |
| Knob pages `0xC00CAFA0` | 3 columns (loop `0xCB014..0xCB1D4`: value `0xA95A4`, text, `0xA0040`); parameter count `0xC00B0594`; pages `(n+2)/3` via `0xC00DB5A0` | medium-high | |
| **Tab row** | loop `0xC00CB1E4..0xCB27C`: per tab, text from `0xC00BBA2C(slot)` with `"%s"` (`0xC00EC8C8`, first tab) or `"%d"` (`0xC00EC8CB`); state 0 current, 1/2 left/right; drawn with **`0xC00AB238(view, x, y 0, state, text)`** (returns width). Softkeys via `0xC009F834`: TAP, EXIT, PAGE | medium | |
| A/B tag hook | after the tab loop, at the call to `0xC00BB92C(slot)` (`0xC00CB284`) or the end (`0xCB2E4`). A15 = slot, B11 = view. Tab row y 0-8; knob area clear y 11-53 (`0xC00AB1B4`) | medium | |

## 6. Byte 17 of each packed slot block (confirmed free)

| what | address | conf | evidence |
|---|---|---|---|
| Pack `0xC00B8474` | loop `0xC00B8444`: `0xC00D382C(dst, src, 18, 11 fields, widths 0xC00EC2F8)` x6 | high | |
| `0xC00D382C` | `memset(dst, 0, 18)` first (`0xC00D3840`), then ORs fields into bytes 0-16 (136 bits); writes to 17-20 are `old \| 0`. **Byte 17 is 0 after pack** | high | `0xD38A6-0xD38F4` |
| Unpack `0xC00B8294` | `0xC00D3740`: clears dst, per field a 5-byte window shifted and masked; for the last field byte 17 is loaded but **masked out** (width 8) | high | `0xD3764-0xD3828` |
| Others | IS_DIRTY compares the unpacked patch; SysEx and flash move the 122 bytes as they are | medium | |
| Caveat | block 5 pack stores up to byte 110, harmless. A byte 17 written after pack (as `rec_save` / `pack_dump` do) is never cleared before the flash write | high | |

## M3a hooks (2026-10-18, TI dis6x of the whole 2.10 OS image)

Grep of every decoded `CALLP`/`B` target, plus a search for the three addresses as literal
words and as `MVK`/`MVKH` halves: **each function has exactly one caller**, a 32-bit `callp`
(its 21-bit displacement is retargeted; the op, the p-bit and any parallel instructions stay).
Each wrapper (`asm/mixer/mixer.S`, vectors +96 / +104 / +112) moves `LAYOUT` and then jumps to
stock with A4 / B4 / B3 untouched.

| hook | call site | stock target, arguments | slot(s) it acts on | wrapper |
|---|---|---|---|---|
| Move | `0xC00B76A4` `callp 0xC00B6BC4 \|\| mv A12,A4 \|\| mv A11,B4` (screen-3 key handler, knob 1 turn while lifted; header packet, p-bit 1) | swap(A4 = old row, B4 = new row) | rows -> slots with `0xC00B6BAC`: count - 1 - row, count = `0xC00B6BA0` -> `0xC00C0818` = word `0xC009C068` | swaps `LAYOUT[a]`, `LAYOUT[b]` (both stores in one execute packet) |
| Add | `0xC00A7BE0` `callp 0xC00C22F4 \|\| ldw *B5[B4],A4` (screen-33 keys `0xC00A7A6C`, ENTER, only when `B14[88]` = 33; A4 = id from `0xC00ECAC8[row]`) | add(A4 = effect id) | insert slot A11 = `B14[32]` + `B14[33]` (`0xC00C2310`; set by `0xC00C1FE0`: anchor slot, side 1 = left); slots insert..count-1 move up one (`0xC00C2394`-`0xC00C2460`); no early exit; count < 6 is checked before screen 33 opens (`0xC00C2018`) | bus = `LAYOUT[anchor]`; `LAYOUT[5..ins+1]` = `LAYOUT[4..ins]`; `LAYOUT[ins]` = bus |
| Delete | `0xC00A8294` `callp 0xC00C2030`, plain (p-bit 0; screen-2 keys `0xC00A8238`, event 34 with row != 0) | delete(), no arguments | slot under the cursor: `0xC00C2098`-`0xC00C20C6` = word `0xC00EE748[6 * view + cursor]`, view = word `0xC009D8F8` (`0xC00BA34C`), cursor = signed byte `0xC009C064` (`0xC00C0834(0)`); slots d+1..count-1 move down one, the last is emptied. **count = 1**: no shift, `0xC00ABACC(0, 0)` empties slot 0 (`0xC00C22D4`) | same lookup; `LAYOUT[d..4]` = `LAYOUT[d+1..5]`, `LAYOUT[5]` = PRE (count 1: moves the empty slots' buses) |

**Before or after stock.** Each stock function starts with the effect semaphore `B14[191]`, the
fade-out `0xC00DF724` (a ramp, not a wait), `B14[98]` = 1 and the slot mutes `0xC00D7B4C`
(both slots for a move, all six for add / delete): microseconds after entry. The slow parts
run with the slots playing again: the move's per-slot delay memory swap `0xC00CB300` after the
fade-in, the add / delete type change `0xC00ABACC` after the semaphore post. So `LAYOUT` moves
**before** stock: the effects play on the wrong bus only for that short stretch at the start
(at most one 8-sample block, longer only if another task holds `B14[191]`). The move's two
bytes go in one execute packet, so the audio never sees a duplicated bus; the shifts are
byte by byte, which can't matter because no effect has moved yet.

**Edited mark.** Stock already marks the patch edited (the records move); with `dirty`
comparing 18 bytes, `LAYOUT` vs the saved buses reads dirty too. No extra call.

Considered and not used: the `0xC00B86E4` (apply) calls inside the move (`0xC00B6D40`) and
add (`0xC00C24C4`) run while the slots are muted, with the slots in A11 / A13; but delete's
slot is gone from the registers there, and the call-site wrappers keep the three alike.

## M3b: the new Effect Chain screen (2026-10-19, TI dis6x of the 2.10 OS)

What `asm/mixer/chain_keys.c` relies on. Confidence: **high** = read in the code
path, **medium** = inferred, not seen run.

**Event ids reaching the screen (high).** In the menu mode (`B14[80]` = 11) the main UI loop
(`0xC00ACDB0`) sends every event to the screen key dispatcher `0xC00A82AC` (call at
`0xC00AD1EC`); after each one (but 232) it runs `0xC00ACD84` (edited mark, AUTO SAVE timer).
Key table entry: event in the dispatcher frame `+8`, knob steps `+12` (stock stubs:
`lddw *+B15[1], A5:A4`), return with A4 = redraw through `0xC00A83C0`.

| id | event | stock play-mode handler |
|---|---|---|
| 32 / 33 | footswitch press / release | |
| 34 | knob 1 press | |
| 64 | knob 2 press; **also** the redraw request our poll / CC / the looper post | |
| 65 | knob 2 release (EXIT) | `0xC00AC790` |
| 66 / 67 | knob 3 press / release (OPEN, PAGE) | `0xC00AC778` (timer 3) / `0xC00AC634` |
| 68 / 70 | cursor up / down press | `0xC00AC60C` (timers 4 / 5) |
| 69 / 71 | cursor up / down release: type +1 / -1 | `0xC00AC450` (B4 = 43 / 45) |
| 72 / 74 | cursor left / right press | `0xC00AC424`: `0xC00C7D60(1)` / `0xC00C7D50(1)` start timers 6 / 7 |
| 73 / 75 | cursor left / right release | `0xC00AC30C` (stops them) |
| 160-162 | knob 1-3 turn, A5 = steps, + = right on screen = earlier in the signal | |
| 227 | timer 3 (knob 3 hold) | `0xC00ABBE8` |
| 230 / 231 | timer 6 / 7: cursor left / right **hold** (add) | `0xC00AB968` |
| 232 / 233 | AUTO SAVE timers 8 / 9 | |
| 225, 226 | **unused by stock**: 225 is our knob 2 long press | |

Timers start / stop with `0xC00C7C80(timer, on)` (wrappers `0xC00C7D60` timer 6,
`0xC00C7D50` timer 7). In the menu mode the play handlers never run, so **no cursor timer
starts**: chain_key starts / stops 6 and 7 itself on 72-75. No timer exists for knob 2, so
the long press is ours: `chain_poll` (every 16 ms, from mixer.S `poll`) counts polls with
knob 2 down in `SW_STATE` `0xC009DF90` (bit clear = down, knob 2 = bit 0: **medium**) and
posts 225 (`EVENT_POST 0xC00CBF40(*(B14+656), 225)`) after 38 polls (0.6 s); the release
that follows is not EXIT.

**Stock add path (high).** `0xC00AB968`: count < 6 (`0xC00C2018`), else the popup
`0xC00CCB00(0, 0xC00EBD5F, 0xC00EBD5E, 1000)` ("MAX EFFECT UNIT!"); `B14[80]` = 11;
`0xC00C1FE0(slot, dir)` stores `B14[32]` (ANCHOR) = slot, `B14[33]` (SIDE) = (dir == 1);
`SET_SCREEN(33, 0)`. The add itself (screen 33 ENTER, `0xC00C22F4` via mv_add) inserts at
ANCHOR + SIDE. Screens 32 / 33 keys `0xC00A7A6C` (stub `0xC00A832C`, shared): ENTER = 32 or
34, then `B14[80]` = 0 (play) whether it added or cancelled (row 4).
**Where screen 33 returns: always play mode**, so we wrap the stub's callp at `0xC00A832C`
(`s33_keys`): after stock, if the add came from the chain (`UI_FROMCHAIN` = 2) and the mode
is 0, back to `SET_SCREEN(3, -2)` in mode 11.

**Knob pages EXIT hook (high).** `0xC00AC790` (event 65 in play mode): if the knob pages
show (`VIEW_KNOBS` `0xC009D398` != 0), `callp 0xC00CCD18 || mvk 1, A4` at **`0xC00AC804`**,
then `VIEW_KNOBS` = 0 and redraw. We retarget that callp (`kp_exit`): stock, then if opened
from the chain (`UI_FROMCHAIN` = 1) mode 11, `SET_SCREEN(3, -2)`. Opening them from the chain:
`B14[80]` = 0, play cursor byte `0xC009C064` = the cursor whose slot
(`0xC00BA2D8(cursor)` = `CURSOR_SLOTS[6 x VIEW + cursor]`, runtime table `0xC00EE748`) is
ours, `VIEW_KNOBS` = 1 (play draw `0xC00BA9D8` reads index 0). The same cursor lookup is
how stock delete `0xC00C2030` finds its slot. **Medium:** that every slot has a cursor in
the current play view.

**Type change (high).** id = word `0xC009BF5C + 44 x slot`; next = `0xC00CA670(id, dir)`;
if next >= 0 and != id, `0xC00ABACC(slot, next)` (a nonzero return shows a popup via
`0xC00AB540`; we skip it).

**Effect state (high).** count `0xC009C068`; ON = record word `0xC009BF58 + 44 x slot` != 0
and bit slot clear in the DSP-off mask `0xC009C060`; name = `0xC00B056C(slot, 1)` (10 chars,
two lines of 5).

**Screen entry.** `SET_SCREEN 0xC00A75E0(s, row)`: `B14[88]` = s; row < 4: `B14[89]` = row.
The menu enters screen 3 with row 0, then `0xC00B6D84` sets `B14[89]` = count - 1 (>= -1).
We mark our own returns with row -2: any other row is a fresh entry (UI reset).

**Draw handlers (high).** Draw table entries take no arguments and finish by jumping to
`DRAW_DONE` `0xC00A9404` (screen 3: `0xC00A93F0` = `callp 0xC00B71CC`, `bnop 0xC00A9404`).
**LCD frame buffer:** `0x11816800 + frame x 1024`, page format: byte `fb[(y >> 3) x 128 + x]`,
bit `y & 7` (bit 0 on top). Blit `0xC009F9B0(frame, x, y, w, h, src)` copies a page-format
source (w bytes per page row) and ORs the dirty mask `0xC00EEBB0 + frame`; at y = 0 it is a
plain copy. chain_draw's row-major buffer is converted to pages and blitted whole, frame 0.

**Free DDR and the C section (high).** The MOD code area is `0xC00F2000`-`0xC0102000` (64 KB,
RAM test region 1; the looper's buffer starts at `0xC0102000`; the last OS section ends
`0xC00F1364`). Users: scroll `0xC00F2100`, looper `0xC00F2200`, midi-cc `0xC00F2800`, looper
services `0xC00F3000`, m0-probe `0xC00F3100`, mixer.S `0xC00F6000`-`0xC00F7280`. **The C
section is at `0xC00F8000`** (about 19.5 KB with chain_draw.c and its 2 KB of buffers,
ends `0xC00FCC40`). B14 is the constant `0xC00EF748`, so the C (far data) reads OS variables
at absolute addresses and never uses B14; built with no RTS (a helper call fails the link).

## Open questions and pedal probes

1. **Cover width 38 vs 33**: photo the stock screen; decide whether M3 reuses the 38-px bitmaps.
2. **Side scroll arrows**: not found; photo with 4+ effects.
3. **FX_TABLE after a swap**: read `0xC00EE930[0..5]` after a stock lift-and-move; if a slot stays `0xC00E0784` (mute), our hook must call `0xC00D7B20(state)`.
4. **Bus layout during a move**: done in M3a (section "M3a hooks", before stock, not near `0xC00B6CF4`). Pedal check: no click when moving / adding / deleting in Parallel.
5. **New screen hooks**: overwrite `0xC00EEFA8` and `0xC00EEBBC` with our stubs; reuse the cover drawer `0xC00A89B4`, the swap `0xC00B6BC4`, refresh `0xC00B6D94`, and the crane `0xC00B74F4` / `0xC00B7428` if kept.
6. **Free screen ids**: 11 is unused (13, 14 MIDI, 15 MIXER).
7. **Not examined**: `0xC00AA3D8` (play-mode cover view), `0xC00BB284`, `0xC00BB1A0(slot, mask)`, `0xC00C3A60` / `0xC00C3A78`, `0xC00D2E20` / `0xC00D2DEC`, footswitches on screen 3.
8. **Lift bookkeeping**: show `B14[151]`, `B14[150]`, `B14[98]`, `B14[89]` on a debug page while moving.
