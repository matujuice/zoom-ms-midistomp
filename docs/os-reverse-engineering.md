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
| Entry (`_c_int00`) | `0xC00DDCC0` | sets SP `0x1180CEF8` (L2), DP/B14 `0xC00EFCC0` |
| `.cinit` copy table | `0xC00F17F8`-`0xC00F1958` | TI RLE (delimiter byte, `delim n v` = n copies, `delim 0 hi lo v` = 16-bit run, `delim 0 0 0` = end) plus zero-init records |
| Zero-initialised RAM | `0xC0000000`+`0x9DFAC`, `0xC0200000`... | six `0x7800` and six `0xAC440` blocks at `0xC0200000`-`0xC0636980`, one block per effect slot (inferred: delay memory) |
| Task table | `.cinit` data | `Task_MainApp 0xC00AD464`, `Task_UpdateUI 0xC00BA644`, `Task_MIDI 0xC00AEE98`, `Task_UpdateLED 0xC00C760C`, `Task_SwitchNrmlSpdRead 0xC00CA620`, `Task_TunerService 0xC00DC8A0` |

Free RAM is not settled yet. `0xC0100000`-`0xC0200000` holds data referenced
by an overlay-style table at `0xC00EE788` (source pointers `0xC0198000`...), so
it is not assumed free.

### MIDI receive (`Task_MIDI`, `0xC00AEE98`)

- Reads bytes from a ring buffer at `0xC0086B90` (read index `B14+224`, write
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
  without code changes; it needs a flash test, not a patch.
- **CC 0** value 0/1 is stored at `B14+172` (bank select, unused with 50 patches).
- **CC 74 / CC 75** switch the UI into states 5 / 6 (value >= 64) or back.
- Every other CC is ignored.

### SysEx parameter edit

- Command byte (`F0 52 00 58 <cmd>`) stored at `0xC0087BA0`; per-command byte
  handlers in tables at `0xC00EF258` and `0xC00EF280`.
- `0x50` editor mode on (sets `B14+344`), `0x51` off. Parameter edits are only
  accepted while editor mode is on.
- `0x31 <slot> <param> <lo> <hi>` stores slot `B14+245`, param `B14+246`,
  value `B14+248`, then runs at `0xC00AED70`:
  `fx_set_param(slot, param, value, 0, 1)` at `0xC00BAEE0`, guarded by
  `Semaphore_pend/post` on the handle at `B14+784` (`0xC00C7C60` / `0xC00D70C0`),
  then a UI refresh (`0xC00ACEA4`, `Event_post(B14+676, 0x40)` via `0xC00CC680`).
- Param 0 is on/off. Patch effect data: 44 bytes per slot at `0xC007BF58`
  (11 words, word 0 = on/off).

This is the path the v0.2 MIDI CC patch reuses. Effect Manager writes effects
over the same SysEx path (issue #15), so the CC patch must leave the SysEx
handlers unchanged.
Tested 2026-10-07 on Luca's MS-60B with the MOD 0.1 build: using Effect
Manager in normal mode left the modded OS intact (MOD 0.1 still shown).

### Still open for issue #2

Button/knob handlers in `Task_UpdateUI`, the audio chain loop, display drawing
behind `Semaphore_LCDUpdate`, and a confirmed free-RAM region.

### Planned MIDI CC patch (issue #4, not built yet)

Design worked out in the v0.2 thread, for the next build thread to implement:

- **Space for new code:** the OS sets L2 to 128 KB cache (`L2CFG` value 3,
  read from `0xC00ED178`), so L2 SRAM is `0x11800000`-`0x1181FFFF`. Nothing in
  the OS or bootloader references `0x1181DE84`-`0x1181FFFF` (checked: no
  constants or data pointers into it), so about 8 KB there is free. It is
  loaded as an extra AIS section (`AisImage.add_section`).
- **Reaching it:** DDR code cannot `callp` into L2 (out of the ±4 MB range).
  The 24 zero bytes at `0xC00AF408` (padding after a function return, never a
  branch target) can hold a three-instruction far jump. The CC call site at
  `0xC00AF088` (`callp 0xC00AE0F8`) is retargeted to that jump.
- **Handler:** CC numbers outside the map go straight on to the stock
  `midi_channel_msg`. Mapped CCs call `fx_set_param(slot, param, value, 0, 1)`
  between `Semaphore_pend/post` on `B14+784`, then the UI refresh, mirroring the
  SysEx `0x31` path. Knob values are scaled from 0-127 to the parameter's range
  (max at offset 12 of the descriptor returned by `0xC00B07AC(slot, param)`).
  From L2, calls into DDR go through a register.
- **CC map:** effect n (1-6) on/off = CC 10n+4 (14, 24 ... 64; value >= 64 is
  on); knob k (1-9) of effect n = CC 10n+4+k (parameter index k+1). This avoids
  the CCs the stock OS uses (0, 74, 75). Slot count per model: 6 (MS-50G OS,
  MS-70CDR), 4 (MS-60B OS).
