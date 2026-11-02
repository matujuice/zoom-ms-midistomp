# Zoom Effect Manager 2 (third-party tool): what it means for us

Research notes, 2026-10-07. Source: <https://zoomeffectmanager.com/en/>, its
quick-start post, its "editing effect files" PDF and its Telegram changelog
(`t.me/s/zoomeffectmanager_en`). The site was read through search and Gemini
summaries because this environment cannot reach it directly, so exact wording
should be re-checked on the site before relying on a detail.

## What it is

A free (donation-supported), closed-source desktop app for Windows 7+ and
macOS 10.13+ that manages the **effect list** on Zoom pedals. It is not
affiliated with Zoom and is a different program from Zoom's own
"MS-50G Effect Manager".

Supported: MS-50G, MS-60B, MS-70CDR, G1on/G1Xon/B1on/B1Xon (+ AK/K variants),
the Four series (G1, G1X, B1, B1X, A1, A1X), G3n, G3Xn, B3n, G5n.
MS-70CDR+ support was being crowdfunded.

Features:

- Write any effect from any supported pedal to any other ("cross-loading").
- Import the effect list from the pedal, save/load lists.
- **Compressed ("shrinked") effects**, added in 2.1.0: about 15-20 % less flash.
- **Change firmware to another model** (2.1.0 for the Four series, 2.3.0 for
  G3n/B3n). The MS entry is effectively what Luca already did by hand
  (MS-50G 3.10 OS on an MS-60B).
- File-count limit check for the pedal file system (2.3.2).

It does **not** edit patches, routing, MIDI behaviour or the OS. It does not
build custom DSP effects.

## How it writes to the pedal

Two modes, per the quick-start post:

| Mode | What happens | Notes |
|---|---|---|
| Normal mode | Only the selected effects are written, updated or deleted while the pedal runs its normal OS. "The firmware is not changed", so an interrupted write leaves a working pedal. | Effect-list import only works here. Implies the **running OS** accepts file writes over USB (USB MIDI SysEx, inferred: not stated on the page). |
| Firmware update mode | Builds a whole new file system (selected effects plus the other files), erases the old one and writes it. | Uses the boot-time updater mode. All models except G5n. |

"Illegal device connected" (reported by users) is the OS refusing a firmware
built for another model, so there is a model check somewhere in the OS or
file system. Not yet located in our disassembly.

The PDF for MS-50G/60B/70CDR and 1on/Xon only covers hex-editing ZDL text
(control names) and float32 frequency constants in place, keeping the file
size identical. No header offsets or checksums are documented.

## Relevance to our goals

| Our goal | Relevance |
|---|---|
| OS patching | None directly: ZEM never touches the OS in normal mode. Useful as proof that the stock OS has a safe, live file-write path over USB. |
| Flash space | High. MS-60B has only 10 free 4 KiB blocks (see formats.md). The same compression trick could make room for new effects or OS-side data on the MS-60B. |
| MIDI (v0.2) | Indirect but important: normal-mode writes go through the OS's USB MIDI handling. MIDI patches in `Task_MIDI` must not break the SysEx path that ZEM and Zoom's own Effect Manager rely on. |
| Routing, live controls, screen | None. |
| MS-50G / 60B / 70CDR compatibility | Confirms the three share effect formats closely enough to cross-load, matching our "same hardware" finding. |
| Recovery | Firmware update mode rewrites the file system through the updater path. If it also rewrites the OS, using it on a modded pedal would revert our OS. Unknown; worth checking before recommending it alongside our builds. |

## Open questions (filed as #15 and #16)

- What exactly does "compressed" change in a ZDL (stripped ELF sections,
  symbol tables, padding)? Can `zoomms` do the same?
- Does a modded OS still accept ZEM / Zoom Effect Manager normal-mode writes?
- Does ZEM's firmware update mode rewrite the OS or the bootloader?

## Other tools found during this search

- **g200kg/zoom-ms-utility**: a browser (WebMIDI) patch editor for the
  MS-50G/60B/70CDR, <https://g200kg.github.io/zoom-ms-utility/>. Likely the
  best public reference for the MS patch SysEx messages, which matters for
  MIDI program change (#3). Not read yet (blocked here).
- **andresdemarco.info/ZOOMFIRMWARE/**: collection of Zoom effect-hacking
  resources, including per-model effect capacity figures. Not read yet.
