# Main OS and bootloader: reverse-engineering notes

Status as of 2026-10-07, from the MS-60B v2.10 updater (cross-checked against
MS-50G v3.10 and MS-70CDR v2.10).

## Getting a disassembly

```sh
scripts/build-c6x-binutils.sh                          # GNU binutils, target tic6x-elf
zoomms updater-parts firmware/<updater>.exe --out work/ms60b
zoomms ais work/ms60b/129_main_OS.bin --elf work/ms60b/os.elf
/opt/c6x/bin/tic6x-elf-objdump -d work/ms60b/os.elf > work/ms60b/os.dis
```

The whole MS-60B OS decodes (about 108k lines, compact 16-bit instructions
included, no undecodable words).

## Boot images

Both parts are TI AIS scripts that parse cleanly end to end:

| | Bootloader (BIN/136) | Main OS (BIN/129) |
|---|---|---|
| Identical across models | yes | no (same codebase, ~99% shared strings) |
| Version string at end of part | `1.10` | `2.10` + `Zoom Corporation` |
| Entry point (MS-60B) | `0xC03C7EC0` | `0xC00CDEA0` (TI C runtime start) |
| Loads into | DDR `0xC03Axxxx-0xC03Exxxx` | L2 RAM `0x1181xxxx` + DDR `0xC008DEA0-0xC00E175C` |
| Setup before load | PLL config (function 5), DDR config (function 2), one SYSCFG register write | same |

No checksum or signature is visible in either part: after the AIS stream the
region is 0xFF padding plus the version string. Whether the updater or the
bootloader verifies something else is not yet known.

The L2 at `0x118xxxxx` and DDR at `0xC0000000` match the TI C674x / OMAP-L13x
memory map (inferred).

## Software stack

Both images are built on TI-RTOS (SYS/BIOS, `xdc.runtime` strings). Named
tasks and events give a first map of the OS:

- OS: `Task_UpdateUI`, `Task_UpdateLED`, `Task_MIDI`, `Task_TunerService`,
  `UsbTask`, `UsbTestMidi_Task`, `Semaphore_LCDUpdate`, `Semaphore_LedTempo`,
  `Event_USBAudioAppCtrl`, file-system error strings, `CMN_DRV.ZDL` / `CMN_BASS.ZDL`.
- Bootloader: `Task_BootMain`, `Task_VersionUpdateMIDI`, `FIRMWARE UPDATE`.

So the USB firmware-update mode lives in the bootloader, not in the OS. A
broken OS should therefore still be recoverable by the official updater as
long as the bootloader is never modified. This is inferred from the strings
and must be confirmed before the first flash of a modified OS.

## Prior work

ZoomMultistompZDL has a TI `dis6x` disassembly of the MS-70CDR OS and has
mapped the ZDL loader (`docs/LOADER-SAFETY.md`). Its addresses are for the
MS-70CDR build and need translating to the MS-60B build.

## MS-50G 3.10 map (v0.2 cycle)

Disassembly made from `ms50g-3.10-stock-keepboot.exe` exactly as described
above. Addresses are for the MS-50G 3.10 build; the MS-60B and MS-70CDR builds
need translating (patches locate code by byte pattern, not fixed address).

### Startup and memory

| What | Address | Notes |
|---|---|---|
| Entry (`_c_int00`) | `0xC00DDCC0` | sets SP `0x1181CEF8` (L2), DP/B14 `0xC00EFCC0` |
| `.cinit` copy table | `0xC00F17F8`-`0xC00F1958` | TI RLE (delimiter byte, `delim n v` = n copies, `delim 0 hi lo v` = 16-bit run, `delim 0 0 0` = end) plus zero-init records |
| Zero-initialised RAM | `0xC0000000`+`0x9DFAC`, `0xC0200000`... | six `0x7800` and six `0xAC440` blocks at `0xC0200000`-`0xC0636980`, one block per effect slot (inferred: delay memory) |
| Task table | `.cinit` data | `Task_MainApp 0xC00AD464`, `Task_UpdateUI 0xC00BA644`, `Task_MIDI 0xC00AEE98`, `Task_UpdateLED 0xC00C760C`, `Task_SwitchNrmlSpdRead 0xC00CA620`, `Task_TunerService 0xC00DC8A0` |

Free RAM is not settled yet. `0xC0100000`-`0xC0200000` holds data referenced
by an overlay-style table at `0xC00EE788` (source pointers `0xC0198000`...), so
it is not assumed free.

### MIDI receive (`Task_MIDI`, `0xC00AEE98`)

- Reads bytes from a ring buffer at `0xC0096B90` (read index `B14+224`, write
  index `B14+228`) filled by the USB MIDI driver, which posts `Event_MIDIDataReady`.
- Running status at `B14+232`, data byte count `B14+235`, first data byte `B14+233`.
- `0xBn` (Control Change) and `0xCn` (Program Change) both call
  `midi_channel_msg` at `0xC00AE0F8` with `A4` = 0 for CC / 1 for PC,
  `B4` = channel, `A6` = CC number or program, `B6` = CC value. The CC call
  site is `0xC00AF088`, the PC call site `0xC00AF0AC`.
- `0xF0` SysEx goes through a state table at `0xC00EF84C`; complete messages
  are executed by `0xC00AE880` (switch on a command code at `B14+208`).

### What the stock OS already does with channel messages

`midi_channel_msg` accepts every channel (omni):

- **Program Change 0-49** loads patch 1-50 (`0xC00B8D34`, current patch at
  `B14+332`). PC 127 has a separate handler (`0xC00AD700`). So issue #3 works
  without code changes. Flash-tested 2026-10-08: PC 0 loads patch 1, PC 9 patch 10.
- **CC 0** value 0/1 is stored at `B14+172` (bank select, unused with 50 patches).
- **CC 74 / CC 75** switch the UI into states 5 / 6 (value >= 64) or back.
- Every other CC is ignored.

### SysEx parameter edit

- Command byte (`F0 52 00 58 <cmd>`) stored at `0xC0097BA0`; per-command byte
  handlers in tables at `0xC00EF258` and `0xC00EF280`.
- `0x50` editor mode on (sets `B14+344`), `0x51` off. Parameter edits are only
  accepted while editor mode is on.
- `0x31 <slot> <param> <lo> <hi>` stores slot `B14+245`, param `B14+246`,
  value `B14+248`, then runs at `0xC00AED70`:
  `fx_set_param(slot, param, value, 0, 1)` at `0xC00BAEE0`, guarded by
  `Semaphore_pend/post` on the handle at `B14+784` (`0xC00C7C60` / `0xC00D70C0`),
  then a UI refresh (`0xC00ACEA4`, `Event_post(B14+676, 0x40)` via `0xC00CC680`).
- Param 0 is on/off. Patch effect data: 44 bytes per slot at `0xC009BF58`
  (11 words, word 0 = on/off).

This is the path the v0.2 MIDI CC patch reuses. Effect Manager writes effects
over the same SysEx path (issue #15), so the CC patch must leave the SysEx
handlers unchanged.
Tested 2026-10-07 on Luca's MS-60B with the MOD 0.1 build: using Effect
Manager in normal mode left the modded OS intact (MOD 0.1 still shown).

### Still open for issue #2

Button/knob handlers in `Task_UpdateUI`, the audio chain loop, display drawing
behind `Semaphore_LCDUpdate`, and a confirmed free-RAM region.

### MIDI CC patch (issue #4, `patches/midi-cc.yaml`)

Built for the MS-50G 3.10 OS only (the patch refuses other builds). Source in
`asm/midi_cc/`; `zoomms asm` assembles it and the patch file carries the bytes,
so building an updater does not need binutils.

- **Space for new code:** the OS sets L2 to 128 KB cache (`L2CFG` value 3,
  read from `0xC00ED178`), so L2 SRAM is `0x11800000`-`0x1181FFFF`. The highest
  L2 address the OS builds with `mvkl/mvkh` is `0x1181DE80` (re-checked over
  the whole disassembly), the bootloader builds none, and no data word points
  past `0x1181DCE0` except one unaligned coincidence. So `0x1181DE84`-
  `0x1181FFFF` (about 8 KB) is free. The boot stack starts at `0x1181CEF8` and
  grows down, away from it. The handler (404 bytes) loads at
  `0x1181DEA0` as an extra AIS section.
- **Reaching it:** DDR code cannot `callp` into L2 (out of the ±4 MB range).
  The 24 zero bytes at `0xC00AF408` (padding after a function return, in a
  plain non-compact fetch packet, never a branch target) hold a far jump
  (`trampoline.S`, 16 bytes). The CC call site at `0xC00AF088`
  (`callp 0xC00AE0F8`, in a compact fetch packet) only has its displacement
  changed, to the trampoline. B3 still returns to Task_MIDI.
- **Handler (`handler.S`):** CC numbers outside 14-73 tail-jump to the stock
  `midi_channel_msg` with all arguments untouched. Mapped CCs do what the SysEx
  `0x31` path does: `Semaphore_pend(B14+784, -1)`,
  `fx_set_param(slot, param, value, 0, 1)`, `Semaphore_post`, UI refresh
  `0xC00ACEA4`, `Event_post(B14+676, 0x40)`. Knob values are scaled
  `(cc * max + 63) / 127` with max from offset 12 of the descriptor returned by
  `0xC00B07AC(slot, param)`; the division is a multiply by `ceil(2^32/127)`
  (exact for every max up to 300000). Calls into DDR go through B5 with B3 set
  to a local return label.
- **What fx_set_param checks itself** (`0xC00BAEE0`): it counts the effect's
  parameters (descriptor flag bit 2 at +44, at most 11) and ignores a param
  past that count, clamps the value to 0..max, and does nothing when the value
  is unchanged. It walks 6 slots, so slots 0-5 are valid on this OS.
- **Tested 2026-10-08** on Luca's MS-60B (MS-50G 3.10 OS, MOD 0.2 build) with
  MIDI-OX: program change loads patches; CC on/off works for effects 1-6 and
  the knob CCs change values. The SysEx `0x31` handler only edits slots 0-2
  (slot 4 is a patch-level setting, 3 and 5 are ignored), but calling
  `fx_set_param` directly works for all six slots.
- **CC map:** effect n (1-6) on/off = CC 10n+4 (14, 24 ... 64; value >= 64 is
  on); knob k (1-9) of effect n = CC 10n+4+k (parameter index k+1). This avoids
  the CCs the stock OS uses (0, 74, 75). Slot count per model: 6 (MS-50G OS,
  MS-70CDR), 4 (MS-60B OS).

### Tempo (MS-50G 3.10)

- The patch tempo is a setting object at `0xC00EE3D8` (in `.cinit` data):
  value pointer `0xC009C06C` (an int in the current patch buffer, right
  after the six 44-byte effect slots), min 40, max 250, name `TEMPO`, change
  callback `0xC00B9A44` at +36. `0xC00C0A2E` resets an out-of-range tempo to 120.
- `0xC00CAC64` is the generic `set_setting(setting, value, notify)`: clamps
  to min/max, does nothing when unchanged, stores, runs the callback.
- The tempo callback takes the effect semaphore (`B14+784`), retunes the
  effects (`0xC00C4064`), releases it, and with `notify` set sends the new
  tempo to an editor over SysEx (`0xC00AF2D0`, only while editor mode is on).
- Tap tempo is `0xC00B9DA8`: times taps with `Clock_getTicks` (`0xC00DF360`,
  1 ms), bpm = 60000 * taps / total ms (unsigned divide `0xC00DCA20`), clamped
  to 40..250, then `set_setting(0xC00EE3D8, bpm, 1)`.
- Matches the effects-pack findings (`zoom-ms-zdl-effects-pack`,
  docs/TEMPO-SYNC.md section 7): the pedal sends `31 03 08 <tempo>` when the
  tempo is tapped (that is the `notify` SysEx), and the incoming `31 03 08`
  is not a tempo edit (the `0x31` handler only edits slots 0-2). Stock
  sync-aware effects (TAPEECH3 and friends) ask the firmware for the tempo;
  no route was found for a custom ZDL to read it.
- `Task_MIDI` ignores realtime bytes (`0xF8`-`0xFF`): the branch at `0xC00AF0C6`
  skips straight to the loop end at `0xC00AF0F8`.

Task stacks (from the `.cinit` task table): `Task_MainApp` and `Task_UpdateUI`
8 KB, `Task_MIDI`, `Task_UpdateLED`, `Task_SwitchNrmlSpdRead`,
`Task_TunerService` 2 KB.

### MIDI clock patch (issue #5, `patches/midi-clock.yaml`)

Built for the MS-50G 3.10 OS only. Source in `asm/midi_clock/`.

- **Hook:** every received byte ends Task_MIDI's loop at `0xC00AF0F8`
  (`ldw *+b14(224),b0`, a 32-bit word in a header fetch packet with no
  parallel bits), with the byte saved at `B14+234`. That word becomes
  `callp 0xC00A1A50`; the hook runs the replaced load before returning to
  `0xC00AF100`. Only callee-saved A10 is live there.
- **Trampoline:** 16 zero bytes at `0xC00A1A50`, after `bnop b3,5` at
  `0xC00A1A4C`, the last four words of a plain fetch packet, not a branch
  target. Far jump to the handler at `0x1181E040` (L2, after the CC handler).
- **Handler (`clock.S`):** any byte but `0xF8` returns at once. For a tick it
  (since fix3 on Task_MIDI's own stack) reads
  `Clock_getTicks`, restarts after a gap of more than 250 ms, and on every
  24th tick completes a beat, whose time is the sum of its 24 tick times
  (fix7), kept in a ring of 8 (differences mod 2^32, in 24ths of a ms).
  From the third beat on, the last two beats give a quick tempo (10 x bpm =
  (28800000 + span/2) / span); 4 BPM or more from the tempo applied last and
  within 2 BPM of the previous beat's quick tempo (or the first tempo after
  the clock starts) is applied at once and the average restarts. Otherwise,
  with 4 to 8 beats in the ring, their average (10 x bpm = (n x 14400000 +
  span/2) / span) is applied only when it is 0.8 BPM or
  more from the tempo applied last. Tempos are clamped to 40..250 BPM. A
  tempo changed by hand holds until the clock tempo changes or the clock
  restarts.
  Applying is `set_setting(TEMPO, bpm,
  0)` then `Event_post(B14+676, 0x40)` for the UI task. Variables: 64 bytes at
  `0x1181E3C0` (`0x1181E700` from v0.4), loaded as a zero section.
- Start, stop and continue (`0xFA`/`0xFC`/`0xFB`) are ignored (until v0.4,
  see "MIDI transport block").
- **Flash tests 2026-10-08:** the first build never changed the tempo. A
  diagnostic (`diag.S`: CC 80 sets the tempo, 24 clocks add 1 BPM) showed
  clock bytes reach the hook and `set_setting` works; a second (`diag2.S`,
  no smoothing) followed 120 and 90 BPM correctly. So the fault was in the
  smoothing step, which compared against a direct read of `0xC009C06C`;
  why that read misled it is not known. The smoothing now compares against
  its own last applied value.
- **fix1 flash test:** the tempo followed the clock, but the pedal froze on a
  tempo change while a delay was on (not with the delay off). fix2 drops the
  direct UI refresh (`0xC00ACEA4`) after the tempo change and only posts the
  UI event, so all drawing stays in the UI task; the private stack may now
  use everything down to the variables (about 7 KB). Cause not confirmed.
- Then Luca checked on fix1: tap tempo with the delay on does not freeze, and
  turning the delay's TIME by CC (v0.2 handler, which also redraws from
  Task_MIDI) does not freeze. That makes the redraw an unlikely cause and
  leaves the private L2 stack as the main difference from stock paths: the
  delay's tempo code (called per slot by `0xC00C4064`, slot state at
  `0x11F03000 + 212 * slot`) ran on it. fix3 keeps fix2 and runs on
  Task_MIDI's own stack.
- **fix3 flash test:** no freeze. But a stock delay went quiet and restarted
  every beat or two even at a steady clock. Stock tap tempo restarts the
  delay the same way, so every `set_setting(TEMPO)` restarts it. The
  manual-change check (tempo read through the value pointer compared with
  the last applied value) never matched, so the tempo was re-applied on
  every beat. fix4 drops that check and applies only a new tempo.
- **fix4 flash test:** steady at 90 and 120 BPM; at 140 the delay still cut
  out now and then. A two-beat span is 857 ms there and 1 BPM is only about
  6 ms of it, so clock jitter flipped the rounded tempo between 140 and 141
  and each flip re-applied it. fix5 measures over 8 beats and needs a change
  of 0.8 BPM or more (about 20 ms of an 8-beat span at 140 BPM).
- fix5 needed 8 beats to lock and to follow a change; Luca wants it quick.
  fix6 keeps the 8-beat average for holding steady and adds the 2-beat
  quick path for jumps (locks 2 beats after the clock starts, follows a
  change in about 3). A host-side simulation with ±3 ms beat jitter gave one
  apply per tempo change at 90-180 BPM and at most two extra near 250.
- **fix6 flash test:** follows and holds steady at the tested tempos, but at
  220 BPM the delay still cut out after a while. fix7 times each beat by the
  sum of its 24 tick times instead of one tick, which cuts the effect of
  jitter about five-fold, and applies a jump only once two quick readings
  agree, so no in-between tempo is applied. Simulated with up to ±8 ms tick
  jitter: one apply per tempo change from 40 to 250 BPM.
- **Fetch-packet padding:** new sections are now zero-padded to a whole
  32-byte fetch packet (`zoomms asm --section`). A section ending mid-packet
  leaves the rest of that packet as whatever L2 held at boot, and a stray
  word 7 that looks like a compact header (`0xE...`) would change how the
  packet decodes. The CC handler section went from 404 to 416 bytes.

### MIDI transport block (issue #24, v0.4)

Format and reader: `docs/transport-block.md`. Block at `0x1181FF00`.

- **Start/Stop/clock count:** in the Task_MIDI hook (`clock.S`), which already
  sees every byte. Updates run with GIE cleared (`mvc csr`), so the audio code
  on the same core never sees a half-written block.
- **A periodic context:** Task_MIDI pends without a timeout (it only wakes on
  bytes), so it cannot notice a clock that stopped without a Stop, or a patch
  TEMPO changed by tap or patch load. `Task_SwitchNrmlSpdRead` (entry
  `0xC00CA620`, from the `.cinit` task table) sleeps 16 ms and starts every
  round with `callp Clock_getTicks` at `0xC00CA630` (a 32-bit word in a
  compact fetch packet). Only that call's displacement changes, to a
  trampoline in the 16 zero bytes at `0xC00C8050` (after `bnop b3,5` at
  `0xC00C804C`, nothing branches there), which jumps to `poll.S` at
  `0x1181E800`. `poll.S` returns the time like `Clock_getTicks` does.
- **Why not hook the TEMPO callback:** `0xC00B9A44` runs for `set_setting`
  (tap, menu, clock), but a patch load may write the TEMPO int
  (`0xC009C06C`) without it (not checked); the poll reads the int itself, so
  it catches every path.
- **L2 use from v0.4:** CC handler `0x1181DEA0`, clock handler `0x1181E040`
  (1600 B), clock variables `0x1181E700` (192 B), poll `0x1181E800` (416 B),
  transport block `0x1181FF00` (32 B).
- **fix1 (faster follow):** Luca found the tempo needs 2-4 beats to follow a
  DAW change. The beat path cannot be quicker without jitter flips (its
  windows straddle two beats). `clock.S` now also keeps the last 24 tick
  times and measures one beat every tick; 12 ticks in a row more than 3%
  from the applied tempo, each within 3% of the first, apply their average.
  Host simulation (1 ms clock, up to ±3 ms tick jitter, tempos 60-220):
  changes of 3% or more land in 1.5-2 beats (beat path: 3-4), steady tempos
  are never re-applied, about one change in four gets a second, fine
  correction a few beats later. Changes under 3% still take the beat path.
  **fix1 flash test 2026-10-08:** OK (Luca).
- **fix2 (clocks lost on a tempo change):** with a pack EuGate reading the
  block (effects pack PR #34), Luca saw EuGate sit a fixed amount off the
  beat after each DAW tempo change until the next Start: the clock count
  came out short. Task_MIDI's own receive ring cannot be the cause (4096
  bytes, and the reader task `0xC00CF2E4` stops reading rather than
  overwriting when it is full), so the likely cause is Task_MIDI blocking in
  `set_setting(TEMPO)` while the effects retune, with bytes lost before the
  ring. Not confirmed. fix2 no longer applies the tempo in Task_MIDI:
  `clock.S` stores it in `V_WANT`, and `poll.S` applies it from the
  footswitch task (same calls as before) on its next 16 ms round.

### Settings screen and MIDI SETTINGS (issue #26, v0.5)

Menu (screen 0: DELETE EFFECT UNIT, EFFECT CHAIN, SETTINGS, VERSION) >
SETTINGS (screen 1) > one screen per setting. Source: `asm/midi_settings/`,
patch `patches/midi-settings.yaml`.

- **Screens:** the current screen id is `B14+364`, written only by
  `set_screen(id, row)` at `0xC00A75E0` (32 call sites, all with constant
  ids). List row and top are `B14+368` / `B14+372`; `0xC00A7040` returns
  row + top, `0xC00A72D4(delta, rows)` scrolls.
- **Dispatch:** key events go through a switch on the screen id at
  `0xC00A8300` (table `0xC00EF300`, ids 1-17, then 32-34), drawing through
  `0xC00A93B0` (table `0xC00EF2BC`). Each case is a stub that calls the
  handler and branches to the epilogue (`0xC00A840C`, `0xC00A9468`); the
  event pair sits at `*+B15(8)`: A4 = event (34 enter, 65 exit, 160 knob
  turn with A5 = steps), A4 returned = redraw. Ids 11, 13, 14, 15 fall to
  the menu and are never set.
- **Setting screens:** 1 list, 4 LCD BACKLIGHT, 5 LCD CONTRAST, 6 BATTERY
  TYPE, 7 AUTO SAVE, 8 POWER MANAGEMENT, 10 BYPASS/MUTE TUNER, 12 HOLD FOR
  TUNER/TAP. AUTO SAVE (keys `0xC00A8144`, draw `0xC00A9270`) is the
  pattern: title `0xC00A7378`, rows `0xC009FCE0(0, text, 1, 12 + 9 row)`,
  highlight `0xC00A73A4(row, 0)`, `0xC00A7400(0)`, knob labels
  `0xC009F8F0(knob, text, 0)`; a turn clamps (`0xC00A766C`) and stores.
- **List draw** (`0xC00A88F8`): names from a pointer table (`0xC00ECD68`,
  mvkl/mvkh at `0xC00A8914`), 7x7 icons, 7 bytes each, one byte per column
  with bit 0 at the top (`0xC00EC5A8`, at `0xC00A8930`), scrollbar
  `0xC00A88CC(top, rows)` with rows at `0xC00A89C8`.
- **Stored settings:** 38 words at `0xC009D8F8` (getters/setters
  `0xC00B9B20`-`0xC00B9CE4`), bit-packed LSB first into a 24-byte record,
  flash record 50 (patches are 0-49), with the bit widths at `0xC00EB538`
  (185 of 192 bits used, so bits 1-7 of byte 23 are free). Pack
  `0xC00D3C6C` (via `0xC00B9CE8`, also used by a SysEx dump), unpack
  `0xC00D3B80` (via `0xC00BA090` at boot). The save (`0xC00B9D04`) runs
  when leaving menus if the words differ from a shadow copy at
  `0xC009D860` (compare `0xC00BA128`).
- **Menu (screen 0):** no switch-table entry; the dispatchers' default
  stubs call the menu key handler `0xC00A79B4` (at `0xC00A8360`) and draw
  `0xC00A7460` (at `0xC00A9400`). Entries from the pointer table
  `0xC00ED020` (4, no scrolling), ENTER through the jump table `0xC00EF870`
  (indexes 0-3), EXIT clears `B14+328`. The menu is always entered through
  `set_screen(0, row)`, so row and top are valid. The version screen
  (9, keys `0xC00A7628`) goes back with `set_screen(0, 3)`.
- **Record 51** (4 bytes, "last patch"): saved by `0xC00B86D0(patch)` (callp
  `0xC00B4C94` at `0xC00B86E0`) on every patch change, loaded at boot by
  `0xC00B8DCC` (callp `0xC00B4D4C` at `0xC00B8DD4`), which keeps the word
  only if it is below 50. Stock never uses bits 8-31. Record 50 is saved by
  `0xC00B9D04(words)`, which also refreshes the shadow copy.
- **Font:** `0xC009FCE0` reads signed chars; codes 22-31 are icons
  (6 bytes each from `0xC00EC1B4`, 25 is a note), there is no degree sign.
- **What v0.5 does:** the menu stubs' callps go (via the zero bytes at
  `0xC00BEDF0` and `0xC00C2164`) to `menu_keys`/`menu_draw`: five entries,
  MIDI SETTINGS at index 3, the version entry at 4 (its exit patched to
  row 4 at `0xC00A7638`). Screens 13 (choice) and 14 (MIDI SETTINGS list)
  get switch-table entries; screen 1's key and draw entries are ours too
  (8 rows, TEMPO LOCK last). All lists are drawn by `draw_list`, which does
  what the stock list draw does. The MIDI word (`0x1181EA00`: bits 0-3
  receive off for clock, transport, PC, CC; bit 4 PROG CH START is 0; bits
  5-9 channel, 0 = OMNI) rides in bits 8-17 of record 51 (`rec_save` at
  `0xC00C5D88`, `rec_load` at `0xC00C4AAC`); leaving a MIDI choice screen
  after a change calls `0xC00B86D0`. TEMPO LOCK is bit 5 of byte 23 of
  record 50 (pack/unpack via `0xC00B97E8`/`0xC00BDB44`); leaving its screen
  after a change calls `0xC00B9D04`. `midi_gate` sits in front of both
  Task_MIDI calls of `midi_channel_msg` (CC `0xC00AF088`, PC `0xC00AF0AC`,
  via `0xC00B2FAC`): channel filter, receive off, and with PROG CH START 1
  PC n loads patch n (PC 0 dropped, PC 127 untouched). `poll.S` calls
  `tempo_lock` every 16 ms: for 16 rounds after the patch number changes it
  asks (`V_WANT`) for the tempo of two rounds before the change, if the
  patch load changed it; quiet for 2 s after boot.
- **L2 use from v0.5:** settings section `0x1181EA00` (4000 B, vectors at
  +64); clock handler 1696 B (ends `0x1181E6E0`); poll 448 B.
- **Not checked:** what `0xC00B9D44` (resets the settings to defaults and
  saves, called from `0xC00C5038`) is used for; the MIDI bits keep their
  value through it.

### Tempo screen, HOLD FOR and combos (issue #28, v0.6)

Source: `asm/tempo_hold/` (`hold.S` at `0x1181FA80`, `hold2.S` at
`0x1181FF20`: together they did not fit before the transport block). Patch
`patches/tempo-hold.yaml`; the HOLD FOR choice screen is in `settings.S`.

- **Key loop:** `Task_MainApp`'s loop at `0xC00ACED0` takes events from the
  mailbox at `B14+828` and calls a handler per event with A4 = event, A5 =
  its value; the handler's A4 asks for a redraw. Mode is `B14+328`: 0 = play
  (effect chain and effect screens), 5/6 = tuner, 11 = menu. `B14+348` is a
  pending state every stock key handler cancels first (`0xC00ABA70`).
- **Footswitch:** event 32 (press, `0xC00ACAB0`) starts hold timer 0 and in
  play mode flips the effect under the cursor (`0xC00ABDE4(slot)`, setting
  the flag `0xC009D02C`), except with the tempo screen open and HOLD FOR
  TEMPO. Event 224 (timer 0, 1 s, `0xC00ABE58`) opens the tuner (HOLD FOR
  TUNER) or toggles the tempo screen (TEMPO), and undoes the flip if the flag
  is set. Event 33 (release, `0xC00ACA1C`) taps if the tempo screen is open
  with HOLD FOR TEMPO, unless the hold just fired (`B14+360`).
- **Buttons:** `Task_SwitchNrmlSpdRead` polls 7 switches into `0xC009DF90`
  (bit i clear = down) and posts 64 + 2i on press, 65 + 2i on release.
  i = 0/1 are the knob 2/3 presses, 2/3 change the effect type ('+'/'-',
  press 68/70 starts timers 4/5, release 69/71 at `0xC00AC574`), 4/5 move
  the cursor (+1/-1, press 72/74 starts timers 6/7, release 73/75 at
  `0xC00AC434`). Timers fire events 224 + i after 1 s: 228/229 open effect
  select (`0xC00ABB80`), 230/231 screen 33 (`0xC00ABA90`). Knob turns are
  events 160-162 (`0xC00AC214`), knob 1 press is 34 (`0xC00AC938`: on a patch
  with a tempo effect it taps and opens the tempo screen for 2 s).
- **Tempo screen:** overlay state 2 (footswitch, `0xC00CB964`, stock: until
  closed) or 5 (knob press, `0xC00CB950`, 2 s), set by
  `0xC00CB8A4(0, state, ms)`, read by `0xC00CBA10(0)`; both drawn by
  `0xC00AAC48(0, tempo)` (box at y 29-55, "TEMPO", big digits), called at
  `0xC00BA930`. Tap is `0xC00B9DA8` (40-250 BPM through the TEMPO setting).
  The softkey "TAP" comes from `mvk` at `0xC00CB3C8`.
- **AUTO SAVE:** after every event `0xC00ACEA4` keeps timer 8 (5 s) armed
  while the patch differs from the saved copy (`0xC00B87F4`); event 232
  (`0xC00ACCE0`) then saves. So a flip saves 5 s after the last event, and a
  flip-back before that leaves the patch as saved.
- **v0.6 changes:**
  - State 2 times out after 2 s (`0xC00CB96C`); the stock `0xC00CB964` call
    after every footswitch tap re-arms it. With the
    tempo screen open the footswitch always taps instead of flipping
    (`0xC00ACBD8`, `0xC00ACA40`: the HOLD FOR getter's result is replaced by
    1), so a screen opened by the combo works with any HOLD FOR.
  - `tempo_draw` clears page 7 under the box and writes TURN OR TAP, or MIDI
    CLOCK while the clock is live (CLOCK RECEIVE on and a clock in the last
    0.5 s, like `poll.S`). `knob_hook` turns the tempo with knob 1 in states
    2 and 5 (clamped 40-250, set like tap) and re-arms the 2 s; `tap_hook`
    skips taps while the clock is live.
  - MOMENTARY (settings `V_HOLDM`, the stock word stays 0): `toggle_hook`
    notes slot and time of the flip, `release_hook` flips back after 0.5 s
    or more, `hold_hook` makes event 224 do nothing, and `dirty_hook` (at the
    `0xC00B87F4` call in `0xC00ACCE0`) reports "unchanged" while the
    footswitch is down.
  - `combo_hook` (events 228-231, play mode, nothing pending): with BOTTOM
    and RIGHT down it runs `0xC00ABE58(224)` with the HOLD FOR word set to 0
    (tuner), with BOTTOM and LEFT set to 1 (tempo screen), then puts the word
    back and clears `B14+360`. `swallow_hook` drops the two buttons' next
    releases. BOTTOM = i 2, RIGHT = i 4, LEFT = i 5 (`hold.inc`).
