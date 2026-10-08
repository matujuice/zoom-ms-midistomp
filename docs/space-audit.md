# Space audit: what fills RAM and flash (MS-50G 3.10 OS)

Status 2026-10-08. Read-only research for "where can new code and data go,
and what could be removed, reworked or compressed". All addresses are for the
MS-50G 3.10 build (the OS on Luca's MS-60B), from
`ms50g-3.10-stock-keepboot.exe` decoded as in `os-reverse-engineering.md`.
"No static reference" means no address constant (`mvk`/`mvkh` pair, data
word, `.cinit` record) points into the range; it does not prove the range is
untouched at run time (see issue: RAM canary test).

## Short answer

Space is not as tight as the 8 KB L2 gap suggests. The tight resource is
**fast on-chip RAM**, not memory in general:

| Resource | Size | Used | Free or likely free | Status |
|---|---|---|---|---|
| OS partition in flash | 704 KB | 355 KB AIS stream | **357 KB** of 0xFF padding | measured |
| SDRAM (DDR) | 8 MB (inferred) | ~5.5 MB | **~2.6 MB** with no static reference | needs canary test |
| Shared on-chip RAM `0x80000000` | 128 KB (if C6747-class) | nothing referenced | **128 KB** | inferred, needs canary test |
| L2 SRAM `0x11800000` | 128 KB | 119.6 KB | **8.4 KB** `0x1181DE84`-`0x1181FFFF` | measured (v0.2 thread) |
| L1D SRAM `0x11F00000` | part of 32 KB | 15 KB | unknown split | not measured |
| Code alignment holes in `.text` | 115 holes, 24-35 B each | | ~3 KB, each fits a 3-instruction far jump | measured |
| Effect file system | 700 data blocks | 400 on the MS-50G set | **300 blocks (~1.2 MB)** | measured |

The "MS-60B has only 10 free blocks" figure in `formats.md` is for the stock
MS-60B 2.10 file system. Cross-flashing the MS-50G 3.10 updater writes the
MS-50G file system, which has 300 free blocks, unless Effect Manager has since
added effects.

## Flash layout (4 MB SPI flash, inferred)

The part sizes add up exactly to the offsets in the OS's flash table
(`0xC00EEFE0`: buffer `0xC0075C10` of 32 KB, regions at `0x3B7000` and
`0x3DA000`, each `0x23000`):

| Flash range | Content | Used | Notes |
|---|---|---|---|
| `0x000000`-`0x03FFFF` | bootloader (BIN/136) | 145 KB | never touch: recovery lives here |
| `0x040000`-`0x0EFFFF` | main OS (BIN/129) | 355 KB | 357 KB padding; room for extra AIS sections |
| `0x0F0000`-`0x3B6FFF` | effect file system (BIN/137) | 711 blocks | 11 system/table blocks + 700 data blocks |
| `0x3B7000`-`0x3D9FFF` | patches and settings, copy A | 140 KB | inferred two-bank store |
| `0x3DA000`-`0x3FCFFF` | patches and settings, copy B | 140 KB | |
| `0x3FD000`-`0x3FFFFF` | BIN/133 | 7 KB of 12 KB | bitmap-like data |

### Effects (ZDL) in the file system

102 files, 1.43 MB. Each ZDL is a 96-byte Zoom header plus a TI ELF shared
object. Bytes per ELF section, summed over all 101 ZDLs:

| Section | Bytes | Needed at load? |
|---|---|---|
| `.text` + `.audio` + `.const` + `.fardata` + `.switch` | 519 KB | yes, the effect itself |
| `.dynsym` `.dynstr` `.hash` `.dynamic` `.rela.*` `.plt` | 170 KB | yes, dynamic linking |
| `.symtab` + `.strtab` | 323 KB | probably not (static symbols) |
| `.debug_*` | 197 KB | no |
| section headers, `.shstrtab`, attributes | ~190 KB | headers maybe, rest no |

About 520 KB (36 %) is static symbols and debug info. Stripping them would
free roughly 130 blocks. Zoom's loader walks sections (ZoomMultistompZDL
`LOADER-SAFETY.md`), so this must be proven on one effect before applying it
to all. zlib on the whole set gives 652 KB and LZMA 592 KB, but the loader
cannot read compressed files, so stripping is the realistic route
(issue #16).

## RAM map

### SDRAM `0xC0000000`-`0xC07FFFFF`

8 MB is inferred: the SDRAM config (bootloader function 2, `0x1C620` = 16-bit
bus, CL 3, 4 banks, 256 columns) matches a 64 Mbit x16 part, and the OS puts
its uncached DMA buffer at `0xC87D0000`, an alias of `0xC07D0000`, just under
8 MB.

| Range | Size | What | Verdict |
|---|---|---|---|
| `0xC0000000`-`0xC002CFFF` | 180 KB | effect code arena: cleared at boot by `0xC00C8060`, allocated from by `0xC00C81D4` (inferred: ZDL code and data) | vital |
| `0xC002D000`-`0xC009DFAB` | 452 KB | other zero-init globals: three 66 KB buffers (`0xC002D1B0`, `0xC003D9B0`, `0xC0052D0C`), 48 KB at `0xC0068C00`, 32 KB flash sector buffer `0xC0075C10`, two 8 KB task stacks, MIDI ring `0xC0096B90`, SysEx state `0xC0097BA0` | vital until each buffer is identified |
| `0xC009DFB0`-`0xC00F1957` | 350 KB | the loaded OS image: code 274 KB, constants 44 KB, initialised data, vectors, `.cinit` | see "OS image" |
| `0xC00F1958`-`0xC0197FFF` | **~649 KB** | no static reference | likely free; callable from OS code with `callp` (within ±4 MB) |
| `0xC0198000`-`0xC01ADAD1` | 88 KB | five buffers listed in the table at `0xC00EE7A0` (control blocks in L1D `0x11F037B8`...) | vital |
| `0xC01ADAD2`-`0xC01FFFFF` | **~329 KB** | no static reference | likely free |
| `0xC0200000`-`0xC022CFFF` | 180 KB | six 30 KB per-slot blocks | vital (effects) |
| `0xC022D000`-`0xC063697F` | 4.13 MB | six 689 KB per-slot delay buffers (176,400 words = 4.0 s at 44.1 kHz each), pool at `0xC00EE998` | vital, but see rework idea |
| `0xC0636980`-`0xC07CFFFF` | **~1.6 MB** | no static reference | likely free |
| `0xC07D0000`-`0xC07F3FFF` | 144 KB | uncached DMA buffers (used as `0xC87D0000`, `0xC87D4000`) | vital |
| `0xC07F4000`-`0xC07FFFFF` | **48 KB** | no static reference | likely free |

The bootloader runs from `0xC03Axxxx` only during boot, inside the delay
buffers, so it does not claim RAM after the OS starts.

### On-chip RAM

- **L2 SRAM** (`L2CFG` = 128 KB cache, so SRAM is `0x11800000`-`0x1181FFFF`):
  30 KB zero-init at `0x11800000`, six 10 KB per-slot blocks
  `0x11807800`-`0x11816800`, 2 KB, fast code `0x11817000`-`0x1181BF00`,
  boot stack up to SP `0x1181CEF8`, initialised data to `0x1181DE84`.
  Free: `0x1181DE84`-`0x1181FFFF` (8.4 KB).
- **L1D SRAM**: per-slot state `0x11F00000`-`0x11F02370` (six 0x348 + six
  0x2A0 blocks) and `0x11F03000`-`0x11F03B18` (initialised, includes the
  per-slot handler state). How much of L1D is SRAM vs cache was not read.
- **Shared RAM** `0x80000000`-`0x8001FFFF`: every `0x80000000` constant in the
  code is the float sign-bit mask, not an address. With 256 KB L2 the chip is
  C6747/C6748/OMAP-L13x class, which all have this 128 KB block, so it looks
  unused. Slower than L2, faster than SDRAM.
- `0x11E1A300` in the data is 300,000,000 (CPU clock 300 MHz), not L1P.

### MS-60B 2.10 OS for comparison

Same layout with 4 slots: four delay buffers and four 30 KB blocks, so about
1.4 MB more SDRAM is unused on that build.

## OS image

| Section | Size | Content |
|---|---|---|
| L2 code `0x11817000`, `0x1181AB80`, `0x1181D860` | 21 KB | fast routines (audio, float math) |
| `.text` `0xC009DFC0` | 274 KB | Zoom app, TI-RTOS kernel, TI C runtime, TI dynamic loader (`DLE_*`), USB stack |
| constants `0xC00E2640` | 44 KB | 8 KB strings (UI text, xdc.runtime assert/log text), fonts and icons, tables |
| init data / vectors / `.cinit` | 7 KB in flash | RLE-compressed by the TI linker |

Code is dense: only 3 KB of zero padding in `.text`, spread over 115
alignment holes. No large dead function was found by reference scanning:
the two copies of the VERSION and tuner screens are both reached (one by
call, one through a table).

## What could be deleted, reworked or compressed

| Candidate | Gain | Verdict |
|---|---|---|
| Put new code in free SDRAM (`0xC00F1958`+, within `callp` range) as an extra AIS section | ~649 KB | **best option**, after a canary test |
| Shared RAM `0x80000000` for hot code/data | 128 KB | good, after a canary test |
| Strip `.symtab`/`.strtab`/`.debug_*` from ZDLs | ~520 KB flash | worth testing on one effect (#16) |
| Delay buffers sized per effect instead of 4 s per slot | up to ~3 MB SDRAM | big rework of the slot allocator; only if SDRAM ever runs out |
| Remove xdc.runtime assert/log strings and UI text for other models (`Reserve0-16`, bass categories) | ~6-8 KB | not worth it: scattered, referenced from tables, flash and SDRAM are not the limit |
| Compress the OS image | none needed | the OS partition is half empty and `.cinit` is already RLE |
| `UsbTestMidi_Task`, factory test screens | small | leave: may matter for USB MIDI and recovery |
| Bootloader | n/a | vital, never modify |

## Notes for the MIDI CC build (v0.2)

- Two addresses in the v0.2 notes of `os-reverse-engineering.md` look off by
  `0x10000`: `Task_MIDI` loads the ring buffer from `0xC0096B90`
  (`mvk 0x6B90` + `mvkh 0xC0090000` at `0xC00AEE9C`), and the SysEx command
  byte is at `0xC0097BA0` (used at `0xC00AD928`). The initial SP is
  `0x1181CEF8`, not `0x1180CEF8`.
- If the handler outgrows 8 KB of L2, SDRAM right after the image
  (`0xC00F1960`+) is reachable with a plain `callp` from `0xC00AF088`, with
  no far-jump trampoline, once the canary test confirms it is unused.
