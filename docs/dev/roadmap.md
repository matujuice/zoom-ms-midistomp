# Roadmap: Luca's feature list, scoped

Base: from v2.0 every pedal runs one build made from Zoom's **MS-70CDR 2.10 OS**.
The MS-50G and MS-60B run it as a 70CDR with only the L input plugged in (see
[ms70cdr-base.md](ms70cdr-base.md)). v1.2 was the last release on the MS-50G 3.10 OS.
Every feature is a patch file applied to Zoom's OS. Tested pedals: MS-70CDR, MS-50G
(via a tester) and MS-60B.

Status is as of the v2.0 release candidate. Details: [v2.0-brief.md](v2.0-brief.md),
[HANDOFF.md](HANDOFF.md), [repo-refresh-plan.md](repo-refresh-plan.md).

| Feature | Where it lives in the OS | Status | Notes |
|---|---|---|---|
| Flash a modified OS and boot it | build pipeline | **done** | `patches/hello.yaml`, see [flashing.md](../flashing.md) |
| MIDI: program change, CC for parameters and on/off, clock sets tempo, Start/Stop | `Task_MIDI`, USB MIDI | **done** (v1.x) | MS pedals only have USB MIDI, so this needs a computer or a USB-MIDI host box |
| Button combos, HOLD FOR, Tempo Lock, faster scrolling | `Task_UpdateUI` | **done** (v1.2) | |
| MS-70CDR base OS for all three pedals, PEDAL INPUT setting | whole OS | **done** (v2.0) | |
| Routing: parallel buses, split, mono serial, `[ROUTE]` / `[MIX]` nodes, limiter | audio chain loop | **done** (v2.0), beta | the new Effect Chain screen; saved per patch |
| PERFORM MODE: every knob, cursor key and the footswitch assignable, with beat/bar/cycle waits, Lag and Follow | UI handlers + new screen | **done** (v2.0), beta | saved per patch |
| Looper (GRDLOOP): tempo-synced, whole bars | new buffer + firmware services | **done** (v2.0), beta | |
| MASTER meters (spectrum, scope + tuner, stereo, LUFS, in/out) and KALEIDO | display driver | **done** (v2.0) | zero CPU while closed |
| DSP limit 225 -> 300, CPU shown in the MENU title bar | effect loader / DSP budget | **done** (v2.0) | the real CPU ceiling stays, so heavy patches can still click |
| SYSTEM page (version, CPU, per-effect load, MODS) | menu | in progress (v2.0) | |
| Stereo versions of the effects pack | effects repo | in progress (v2.0) | |
| Better Mac updater | `scripts/midistomp_builder.py` | in progress (v2.0) | much easier install |
| PERFORM: one effect per control, a parameter per gesture | PERFORM store + UI | research | after v2.0 |
| More than 6 effects per patch (limited only by DSP) | patch format, chain arrays | research | after v2.0 |
| Browser build and flash with Modwerk | builder | research | no Zoom code hosted; see `docs/dev/modwerk-research.md` once written |
| Effects that talk to each other | transport block + custom effects | partly done | the tempo/transport block (`0x1181FF00`) exists; a modulation bus does not |
| Effect select screen with 5 categories like the MS-50G | UI | planned | not researched yet |

## Order

1. Finish the v2.0 "Before release" list in [repo-refresh-plan.md](repo-refresh-plan.md).
2. Pedal tests of the beta items, then release v2.0 (title `MIDISTOMP v2.0`, notes in
   [../releases/v2.0.md](../releases/v2.0.md)).
3. v2.1: the research items above.
