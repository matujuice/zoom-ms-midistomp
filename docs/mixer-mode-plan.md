# Mixer Mode: build plan (draft for Luca)

v2.0 step 3, on the MS-70CDR 2.10 base. The design is in `docs/v2.0-brief.md`,
"Phase 2: Mixer Mode". This file covers only **what gets built first and in
which order**, so each step ends with something Luca can flash and hear.

```
OUTPUT ← Post ← [MIX] ← Bus A ← [ROUTE] ← Pre ← INPUT
                      ↖ Bus B ↙
```

## What we know and what we don't

- **Known:** each effect gets three buffers from the OS: `ctx[4]` the dry input,
  `ctx[5]` the signal from the effects before it, `ctx[6]` an output it adds
  into (effects pack `build/ABI.md`). The chain is already stereo on both OSes
  (`docs/ms70cdr-port.md`). So routing should be possible without touching any
  effect: give Bus B effects their own pair of buffers, then sum.
- **Not known yet:** where the 70CDR OS sets those buffers for each slot and
  runs the six effects; how it counts DSP load ("DSP Full"); where a patch has
  room to store the bus of each effect and the node settings.

## Steps

| # | What | Luca hears / sees | Model |
|---|---|---|---|
| M0 | **Research, no build:** find the chain runner, the per-slot buffers, the DSP budget and spare bytes in the patch format on the 70CDR OS. Ends with a go / no-go and the hook points | nothing (a report) | Opus, Sonnet for the address work |
| M1 | **Engine with fixed test layouts:** the firmware runs Pre → Bus A + Bus B → sum → Post from a layout picked by a test build (e.g. slots 1-2 Pre, 3 on A, 4 on B, 5-6 Post), 50/50 sum, the safety limiter on the output | parallel effects really in parallel; no clicks; what happens at DSP Full | Opus |
| M2 | **The nodes:** `[ROUTE]` and `[MIX]` with their knob pages in Effect View (Send, Crossfade with the Smooth / DJ / Cut curves, levels, Mode, Output Mode), saved per patch, MIDI CCs. Tested with a **routing probe** ZDL (a sound source, a filter and a delay in one effect, with a BUS: PRE / A / B / POST knob, Luca 2026-10-15); stock effects keep their bus from M3 on | playing Send and Crossfade by knob and CC, patches remember them | Opus engine, Sonnet UI |
| M3 | **Effect Chain screen** rebuilt (two rows, nodes, signal lines, A/B tags in Effect View), **PEDAL INPUT** setting (MONO / STEREO, default MONO: hides Split input and draws one IN), old patches load as Serial | the full design | Sonnet, Opus review |
| M4 | Smart Warning, bus latency matching, effect types table | badges | later |

Each step ends with tests, a real build from Zoom's MS-70CDR updater and a
flash test by Luca before the next one starts, as in the 70CDR port.

## Decided (Luca, 2026-10-15)

- M2 is tried with a routing probe ZDL (sound source, filter, delay, BUS knob),
  several in one patch, before the new Effect Chain screen.
- Parallel and Serial in M2; Split input, Split output and PEDAL INPUT in M3.
- Old patches load as Serial with every effect in Pre.
- M0 starts now.
