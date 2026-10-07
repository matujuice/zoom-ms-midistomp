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
