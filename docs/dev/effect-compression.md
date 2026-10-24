# Effect compression: freeing flash for more effects (#16)

Research, 2026-10-15. Read-only: no firmware code. Measured on the stock
updaters MS-50G 3.10, MS-60B 2.10 and MS-70CDR 2.10 and on the 11 effects of
zoom-ms-zdl-effects-pack (`dist/*.ZDL`).

## Outcome (Luca, 2026-10-15)

Not pursued. Custom effects are already stripped (about 100 bytes per file
left to gain, no block saved), and stripping the stock effects would mean
rewriting all of them. Luca deletes unused stock effects with Effect Manager
instead, so space is not an issue now. #16 closed as not needed. The
measurements below stay for later.

## Short answer

Stock effects carry about 36 % of dead weight: debug info and the static
symbol table, which the pedal never needs. Removing it frees about **230 of
the 700 data blocks** on an MS-60B or MS-70CDR, enough for the whole effects
pack four times over. No OS change is needed, and Effect Manager load and
unload keep working because the file system format does not change.

The pack effects already ship without these sections and load on the pedal,
so the loader is proven to work without them.

## Who is short of space

A MIDISTOMP updater never writes the effect file system (see `flashing.md`;
the MS-50G updater has no file system step). So each pedal keeps the effect
set of its own model, plus whatever Effect Manager added or removed:

| Pedal | Effect files | Data blocks used | Free | Free after stripping |
|---|---|---|---|---|
| MS-50G 3.10 | 101 | 398 | 300 | 432 (+132) |
| MS-60B 2.10 | 143 | 688 | **10** | 238 (+228) |
| MS-70CDR 2.10 | 137 | 681 | **17** | 250 (+233) |

Blocks are 4 KiB with 4090 bytes of payload, so every file is rounded up.
The 11 pack effects take 55 blocks. On a stock MS-60B or MS-70CDR they only
fit after removing stock effects.

Correction: the space audit (2026-10-08, comment on #16) said Luca's MS-60B
has the MS-50G file system with 300 free blocks. That is wrong: cross-flashing
the MS-50G updater leaves the MS-60B file system in place.

## What fills an effect file

Bytes per kind, summed over all effects of each set:

| Kind | MS-50G | MS-60B | MS-70CDR | Pack (11) | Needed? |
|---|---|---|---|---|---|
| code and data (`.text`, `.audio`, `.const`, `.fardata`, `.plt`) | 519 KB | 1064 KB | 1043 KB | 170 KB | yes |
| dynamic linking (`.dynsym`, `.dynstr`, `.hash`, `.dynamic`, `.rela.*`) | 171 KB | 278 KB | 266 KB | 17 KB | yes |
| static symbols (`.symtab`, `.strtab`) | 323 KB | 579 KB | 580 KB | 0 | no |
| debug info (`.debug_*`) | 197 KB | 297 KB | 305 KB | 0 | no |
| section headers | 145 KB | 207 KB | 199 KB | 6 KB | yes (loader walks them) |
| other (attributes, TI section flags, `.shstrtab`) | 40 KB | 57 KB | 55 KB | 2 KB | keep |

## Strip levels

| Level | Removes | MS-60B blocks | Proven? |
|---|---|---|---|
| **A** | `.debug_*`, `.symtab`, `.strtab` and their section headers | 688 → 460 | yes: pack effects have none of these and load |
| B | A + `.c6xabi.attributes`, `.TI.section.flags`, headers of empty NOBITS sections | 688 → 437 | no: pack effects keep these |
| C | B + all section headers | not measured | no, and the loader walks sections (LOADER-SAFETY.md) |

Level A is the one to use. B adds only about 23 blocks for an untested change.

Rewriting a file is more than cutting bytes: in every ZDL (all 392 checked),
`DT_SYMTAB`, `DT_STRTAB`, `DT_HASH`, `DT_RELA` and `DT_JMPREL` in `.dynamic`
hold **file offsets**, not addresses. The debug and `.symtab` sections sit
before `.dynsym`, so a strip tool must move the dynamic tables, rewrite those
tags and the section header offsets, and update the ZDL header's ELF size.
The pack's `build/linker.py` already writes these tags the same way.

## Real compression (LZ) for comparison

The space audit measured zlib at 652 KB and LZMA at 592 KB for the MS-50G set
(1.43 MB), against 880 KB for strip level A. Compressing on top of stripping
would gain more, but the OS would have to decompress every effect at load
time: a patch in the loader, extra RAM, and a format that Effect Manager
does not know (an effect it writes would arrive uncompressed and must still
load). Not worth it while stripping alone frees a third of the flash.

## Zoom Effect Manager 2's "shrinked" effects

ZEM2 2.1.0 writes effects about 15-20 % smaller. Its method is not public
(the site is blocked from here). 15-20 % is close to dropping the debug info
(12 %) or the static symbols (23 %) alone, so it is probably a lighter version
of the same strip. Not confirmed.

## Ways to get stripped effects onto a pedal

| Option | How | Effect Manager | Cost |
|---|---|---|---|
| 1. Builder option | `zoomms build --strip-effects`: takes the stock updater of the user's own model, strips its effect set (level A), adds any extra ZDLs given (the pack), and writes the file system during the MIDISTOMP flash, like the stock MS-60B updater does | load/unload unchanged | resets the effect list to stock + extras; patches that used removed effects lose them |
| 2. Strip tool only | `zoomms strip in.ZDL out.ZDL`; the user writes the stripped files with ZEM2 in normal mode, replacing the originals | unchanged | no flash risk, but one file at a time |
| 3. Use ZEM2 shrink | nothing to build | unchanged | only 15-20 %, method unknown |
| 4. Remove effects | Effect Manager already does it | unchanged | nothing to build; lose effects |

Option 1 needs the user's own model's stock updater, which the builder does
not ask for today (it only uses the MS-50G one).

## Side finding for the effects pack

Stock MS-60B and MS-70CDR effects up to 45 KB (TREM_REV 44,397 bytes,
MNGLD_SP 45,548) boot fine, so the 36 KB boot hang of DirtBox (firmware
limits report, item 11) is not a plain file-size or header SIZE limit. The
loaded code and data may be: the largest stock effect loads 20.8 KB of
segments, Choral (boots) 24.9 KB. Unproven; recorded here for later.

## Effect Manager compatibility (#15)

Luca decided 2026-10-15: only loading and unloading effects with an Effect
Manager in normal mode must keep working. Patch management through Effect
Manager does not matter. Every option above keeps the file system format and
file names, so load and unload are unaffected.
