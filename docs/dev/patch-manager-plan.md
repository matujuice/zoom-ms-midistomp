# Patch manager in Modwerk: plan (draft, 2026-11-06)

Goal: Modwerk's Zoom page lists the pedal's 50 patches with **everything** in them: effects
and knobs, the routing (buses, Input/Master R, output mode, mutes), the mixer settings and
the Perform setup. Back up, restore, copy and reorder patches without losing any of it.

Nothing here is agreed with Modwerk yet. Not built.

## Where the data is

| Part | Where on the pedal | Can a tool read it today? |
|------|--------------------|---------------------------|
| Effects, knobs, on/off, name, tempo | the patch (122 B packed) | yes, Zoom's patch SysEx (what Zoom's editor uses) |
| Bus per slot, Input/Master R, output mode, mutes, solo | byte 17 of each slot block, in the patch | yes, same SysEx: the pedal puts byte 17 in every dump and keeps it on store |
| Mixer settings 0-10 (mode, send, levels, curve, XFade...) | record 50, 16 B per patch at `24 + 16n` | **no** |
| Perform setup | record 50, 208 B per patch at `828 + 208n` (magic `PRF3` at 824) | **no** |

Record 50 is 11228 B (`asm/mixer/chain.h` R50_SIZE). Its layout, the FNV-1a hash that ties
an entry to a patch, and the editor rules are in `modwerk-research.md` sections "Byte 17" and
"Record 50". That section is out of date on Perform: it says 112 B per entry, 6428 B and
`PRF2`; the code says 208 B, 11228 B and `PRF3` (`asm/perform/perform.h:90`,
`perform_store.c:11`). Fix it before we send it.

So the firmware has to open record 50 to the outside. That is the main work.

## Firmware: a small MIDISTOMP SysEx (manufacturer id 7D)

Same header as the hello proposal in `modwerk-research.md` (`F0 7D 4D 53 54 <cmd> ...`), so
the hello can come with it for free.

| Cmd | Host sends | Pedal answers |
|-----|------------|---------------|
| 01 hello | `<nonce>` | `41 <nonce> <major> <minor> <patch>` + feature bits |
| 02 read entry | `<n>` (patch 0-49) | `42 <n> <224 B packed 7-in-8>`: mixer entry n (16 B) + Perform entry n (208 B) |
| 03 write entry | `<n> <224 B packed> <crc:5>` | `43 <n> <status>` |

- **Receive:** our byte hook at the end of Task_MIDI's loop (`asm/midi_clock/clock.S`) already
  sees every MIDI byte. Add a small state machine for `F0 7D 4D 53 54` only; every other byte
  goes on as now (never swallow a byte: Effect Manager uses the stock SysEx path). Cost is one
  compare per MIDI byte, none in the audio path.
- **Write:** check n < 50, the CRC and Perform byte 15 = `0xA5`; copy into the RAM image of
  record 50, then the same save `r50_save` uses on STORE. Values are clamped on load already.
  Refuse while the looper records (a record-store save stalls the UI task).
- **Send:** needs the 70CDR SysEx send routine, still **not mapped** (`modwerk-research.md`
  section 1). Find it from the identity reply (its template is known now: identity-tag) or
  the editor-mode tempo notify. This is the research step; the rest is plumbing.
- **Models:** MS-70CDR first. MS-50G / MS-60B get the same commands once their send routine
  is mapped.
- Stock firmware: Modwerk sends hello; no answer means stock, and the page shows patches
  without mixer and Perform (it works the same, minus those columns).

Rejected: appending record 50 entries to Zoom's patch dump (changes a stock message that
Zoom's editor and Effect Manager parse); exposing record 50 as a fake file (hooks the file
system code, much more risk for the same result).

## Modwerk side

1. Patch read/write over Zoom's patch SysEx (they have no patch code yet; their backup note
   says patches are "backed up separately, by SysEx"). Editor mode on (`50`) / off (`51`).
2. Decode the 122 B patch: effect ids against their effect list, knobs, name, byte 17.
3. With a MIDISTOMP pedal: read the 50 record 50 entries (cmd 02), show mixer and Perform.
4. Backup file: patches + entries in one file. Restore writes the patch first, then its entry.
5. Copy / reorder: move the entry with the patch and recompute the hash when the name or
   effects change (FNV-1a, `asm/mixer/pages.c:196-206`); otherwise the pedal falls back to
   defaults for that patch (see the table in `modwerk-research.md`).

The decoder for record 50 should live in one place both sides can test against: a JSON
description in `vendor/midistomp` (the importer already copies our files), with a test that
reads a captured entry.

## Steps

| # | What | Who | Needs pedal |
|---|------|-----|-------------|
| 1 | Map the 70CDR SysEx send routine | us (deep) | no (disassembly), then a test |
| 2 | Hello + read entry (01, 02) in a test build; `zoomms` gets `hello` and `r50 read` | us | yes |
| 3 | Write entry (03) with CRC; STORE / power-cycle test | us | yes |
| 4 | Fix and send the record 50 / byte 17 spec + this command table to Modwerk | Luca OK first | no |
| 5 | Modwerk patch read/write + the patch page | Modwerk, or us as a PR | yes |
| 6 | Mixer and Perform columns, backup/restore with entries | Modwerk or us | yes |

Steps 1-3 ship in a MIDISTOMP release; v2.0 work and bug fixes stay first.

## Open

- Does Modwerk want to build the page, or a PR from us?
- 7D (non-commercial id) acceptable to them and to Windows MIDI stacks?
- Record 51 (MIDI settings) in the same command, for a full backup?
