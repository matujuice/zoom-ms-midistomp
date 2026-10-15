# Moving MIDISTOMP to the MS-70CDR OS

Decided 2026-10-15: from v2.0 every pedal (MS-50G, MS-60B, MS-70CDR) runs one
build made from Zoom's **MS-70CDR 2.10** OS. Luca has run the stock 70CDR OS on
an MS-50G and an MS-60B: it works like a 70CDR with only the L input plugged.
v1.1 is the last release on the MS-50G 3.10 OS and is frozen.

Why not stereo input on the MS-50G OS instead: `docs/ms70cdr-port.md`
(branch `claude/project-thread-zsb5sp`, which did not work on the pedal).

## Hardware: what differs

From the OS comparison in `docs/ms70cdr-port.md` ([C] confirmed in the
disassembly, [I] inferred):

| | MS-50G / MS-60B | MS-70CDR |
|---|---|---|
| CPU, memory map, peripherals | same | same [C] |
| SDRAM | same map, so same size [I] | same |
| Bootloader (BIN/136), USB IDs | identical | identical [C] |
| Input ADC | one (L) on McASP AXR5 | a second one (R) on AXR4 [C] |
| GPIO 39 | | probably a second SPI flash chip select [I] |

**RAM:** no more RAM on the 70CDR; the same memory map. Its OS lays data out a
little differently (bigger input buffers, B14 data at `0xC00EF748` instead of
`0xC00EFCC0`), so the free regions from the RAM test (issue #19) must be
measured again on the 70CDR OS before the looper relies on them.

**Effects flash:** installed effects and patches must survive the update, as
they always have for Luca: Zoom Effect Manager's firmware switch (MS-60B to
the 70CDR OS) and every MIDISTOMP build so far (made from the MS-50G updater,
whose script never writes the effects area) kept them. Zoom's own MS-70CDR
updater is different: its script also erases and rewrites the effects file
system (BIN/137, 2.9 MB at `0xF0000`, see `zoomms/flash.py`), which would put
the stock 70CDR set (137 effects, 17 free blocks) on every pedal. So the
MIDISTOMP builder sets those two steps to SKIP, like the bootloader steps.
Check on the MS-60B that its bass effects list and load on the 70CDR OS (it
has no OD/DIST category).

## How

The patches stay as they are, with a second set of addresses: every `write:`
and `section:` entry is tagged `model: ms50g-3.10`; the ported ones are tagged
`ms70cdr-2.10`. The asm sources take the addresses from `.equ` lines, so a
port changes those lines and the patch bytes, not the logic.

- **Finding addresses:** 47 of the 70 patch sites match uniquely by their
  normalized code context in the 70CDR OS; 23 need a person (SysEx handler
  tables, padding caves, call sites in changed functions). `asm/` uses 161
  OS addresses plus B14 offsets, which shift too (the model byte is at B14+220
  on the MS-50G, B14+212 on the 70CDR).
- **Who:** the matching and byte regeneration is mechanical (a cheaper model is
  fine); the 23 hard sites and anything in the audio path get a careful
  review. Every port is checked by the existing tests (bytes match source,
  sections don't overlap) and by a flash test.
- **Builder:** `scripts/midistomp_builder.py` takes Zoom's MS-70CDR updater
  (sha256 in `models/ms70cdr.yaml`), builds for `ms70cdr-2.10`, and skips the
  bootloader and effects file system steps (a test checks the flash script).

## Steps (one flash test each)

1. **MIDI port:** MIDI CC (with CC 80/81 patch up/down), clock and
   transport, the MIDI menu. As one build, like v0.2-v0.5 were tested.
2. **UI port:** tempo screen, HOLD FOR, button combos, scrolling, version and
   boot logo.
3. **RAM test** (issue #19 build) on the 70CDR OS: free regions for the
   looper's big buffer.
4. **Looper services** (`docs/looper-services.md`) on the new addresses, then
   Mixer Mode and Perform mode as in `docs/v2.0-brief.md`.
5. **PEDAL INPUT setting** (MONO / STEREO) for the input modes in Mixer Mode
   (the OS can't tell the pedals apart).

Release: one builder and one updater for all three pedals.
