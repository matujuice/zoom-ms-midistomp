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

## M1 test build (2026-10-16)

`patches/mixer-m1.yaml` (source `asm/mixer/`): the engine at DDR `0xC00F6000`, layout fixed at
section +32, slot 0 first: **PRE PRE A B POST POST**. On screen (signal flows right to left):
the 2 rightmost effects are Pre, the 3rd from the right is Bus A, the 4th is Bus B, the 2
leftmost are Post. MIX is 50/50, no limiter yet (a 50/50 sum is never louder than the louder
bus; the limiter comes with the M2 levels). With positions 3 and 4 empty both buses carry the
same signal, so it sounds like stock. The probe's P1 is in the build (`m0-probe.yaml`), its
slot-loop hook (`m0-probe-chain.yaml`) is not: same packet, so P1's FX row and P3 read 0.

`zoomms build <MS-70CDR 2.10 updater> --build-id ms70cdr-2.10 --patch patches/version-1.2.yaml
--patch patches/boot-logo.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml
--patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml --patch patches/scroll.yaml
--patch patches/m0-probe.yaml --patch patches/mixer-m1.yaml --stamp "label=M1 MIXER"
--out "build/out/MIDISTOMP M1 mixer.exe"`

Assembled locally with TI's `cl6x` (CGT 8.5, the source has no macros); GNU binutils is
still the reference (`tests/test_mixer_patch.py`, skipped without it).

**Pedal results (Luca, MS-70CDR, 2026-10-16): works.** Stock-equal with positions 3-4 empty,
parallel drive + chorus/delay heard side by side, effect change and CC 80/81 switches without
clicks.

| patch | declared DSP | BLK min / avg / max | LOAD avg / max | PEAK |
|---|---|---|---|---|
| empty | 0 | 5 228 / 5 291 / 7 038 | 9 % / 12 % | 15 % |
| heavy (Arena, LO-FI Dly, FuzzSmile, Air, StonePha, LOFI Rev) | 293.4 | 32 018 / 35 316 / 42 126 | 64 % / 77 % | 83 % |

- Engine cost is lost in the noise: empty-patch PER AVG 12 204 vs 12 005 in probe v1.
- About **100 cycles per declared unit** ((35 316 - 5 291) / 293.4 = 102; probe v1 gave 95).
- At 293 declared the worst block still had 23 % headroom, so the stock 225 limit is very
  conservative. The final limit is still open (handoff "Later").
- Not checked yet: effects that did not write F in probe v1 (ICE Delay, AnalogDly, Gyre) on
  Bus A or B. If their output does not land in F, copying F cannot route them.
