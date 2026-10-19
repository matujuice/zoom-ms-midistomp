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
Checked 2026-10-15 (Luca, MS-60B switched to the 70CDR OS with Zoom Effect
Manager, which also keeps the effects area): its bass effects list and load,
so a build that skips the effects write gives the same result.

## How

v1.1 is tagged (`v1.1`), so the MS-50G build can always be rebuilt from that
tag. On `main` the patches and asm sources are converted **in place** to the
MS-70CDR 2.10 OS (`model: ms70cdr-2.10`, `builds: [ms70cdr-2.10]`): one set of
addresses, no per-model machinery.

- **Finding addresses:** 47 of the 70 patch sites match uniquely by their
  normalized code context in the 70CDR OS; 23 need care (SysEx handler
  tables, padding caves, call sites in changed functions). `asm/` uses 161
  OS addresses plus B14 offsets, which shift too (the model byte is at B14+220
  on the MS-50G, B14+212 on the 70CDR).
- **Checks:** the existing tests (bytes match the asm source, release sections
  don't overlap), a real build from Zoom's updater (every `expect:` must match
  the 70CDR OS), then Luca's flash test.

## Tasks

Agents need Zoom's updaters, which are never committed; they run where those
files are. Each task ends with tests passing and a real build.

| # | Task | Model | Needs |
|---|---|---|---|
| T1 | **Builder for the 70CDR:** `models/ms70cdr.yaml`, `zoomms/flash.py`, `scripts/midistomp_builder.py` take Zoom's MS-70CDR updater; the bootloader and effects (BIN/137) steps are set to SKIP; a test checks the resulting flash script | Sonnet | - |
| T2 | **Address map:** every OS address and B14 offset used by `asm/` and `patches/` (release set, looper, ram-test) with its 70CDR counterpart, how it was found and a confidence, in `docs/ms70cdr-addresses.md`; uncertain ones flagged | Sonnet | - |
| T2r | Review the flagged addresses | Opus | T2 |
| T3 | **MIDI port:** `midi-cc` (with CC 80/81), `midi-clock`, `midi-settings` | Sonnet | T1, T2r |
| T4 | **UI port:** `tempo-hold`, `scroll`, `version-1.1`, `boot-logo` | Sonnet | T3 |
| T5 | **RAM test port:** `ram-test`, then Luca runs it | Sonnet | T2r |
| T6 | **Looper services port** with the new free regions (done, flash-tested with the Looper ZDL) | Opus | T5 |
| T7 | **PEDAL INPUT** setting | Sonnet | T4 |
| T8 | Mac builder from Zoom's MS-70CDR Mac updater (done 2026-10-19, flash-tested on an MS-50G) | Sonnet | T4 |

T3 and T4 each end with a flash test by Luca before the next starts.

T3 flash-tested 2026-10-15 (Luca, MS-60B and MS-70CDR): boots with effects and
patches kept, MIDI menu saved, Program Change (START NO. 0/1), CC on/off and
knobs, CC 80/81 patch up/down, clock, Start/Stop, MIDI CHANNEL, stereo input
on the 70CDR.

T4 flash-tested 2026-10-15 (Luca): boot logo and v1.1, tempo screen, HOLD FOR
(TUNER / TEMPO / MOMENTARY), combos and tuner EXIT, scrolling with wrap and
bounce, TEMPO LOCK, CC and Program Change.

T6 flash-tested 2026-10-15 (Luca): looper services build with the Looper ZDL
(status box changes, Roll on the bar's first slice) "working well".

RAM test (T5) run 2026-10-15 by Luca on the 70CDR OS: all five regions 0
after boot and after heavy use. Free: 1 `0xC00F3100`-`0xC0197FFF`, 2
`0xC0198000`-`0xC01FFFFF` (bigger than on the 50G, no overlay table there),
3 `0xC0636980`-`0xC07CFFFF`, 4 `0xC07F4000`-`0xC07FFFFF`, 5 shared RAM
`0x80000000`-`0x8001FFFF`.

Release: one builder and one updater for all three pedals; then Mixer Mode and
Perform mode as in `docs/v2.0-brief.md`.
