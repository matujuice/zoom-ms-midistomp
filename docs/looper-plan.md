# Looper v2 plan (with Perform mode)

Status: draft, 2026-10-22. Decisions from Luca's answers; open items at the end.
Code: `zoom-ms-zdl-effects-pack/src/custom/looper/looper.c` (fxid 497) and the
firmware looper services (`asm/looper/`, `patches/looper.yaml`,
`docs/looper-services.md`).

## Decided

| Topic | Decision |
|---|---|
| Who quantizes | One cycle per patch, owned by the firmware grid. The looper's **NEXT** knob alone decides when rec / stop / play / delete land. Perform passes footswitch presses straight through (FX4 Ftsw), no extra wait. |
| Cycle length | The looper keeps its own **CYCLE** knob, so it works outside Perform. When Perform mode has a CYCLE set for the patch, Perform's value overrides the knob. |
| Recording length | **SYNC OWN / SLAVE.** OWN: record from the next NEXT line until the NEXT line after the second press, rounded to whole cycles. SLAVE: record one cycle, then play by itself. Replaces the Length knob. |
| No clock | Grid at the pedal tempo (tap / patch tempo). Bar 1 is MIDI Start, or the first press that records. Perform moves wait for their line the same way. |
| MIDI Stop | New setting **STOP: KEEP / HALT** (see below). KEEP lets the loop play through a Digitakt project change. |
| Mono | A mono loop stores (L+R)/2, not the left input. |
| Memory | CYCLE can be longer than memory (Perform goes to 32 bars). Record what fits, halving as today, and say so in the status box (`REC 4/8`). |

## Knobs

| Page | Knob 1 | Knob 2 | Knob 3 |
|---|---|---|---|
| 1 | **Mix** 0-100 (as today) | **Roll** OFF, 1/2 … 1/32 (as today) | **Sync** OWN / SLAVE |
| 2 | **Next** NOW / BEAT / BAR / CYC | **Cycle** 1-32 bars (Perform overrides) | **Stop** KEEP / HALT |

- Old Length and When/Amount go. Old patches: When maps to Next, Amount to Cycle, Length is dropped (Sync = OWN).
- **Stop KEEP** (default): MIDI Stop and clock loss are ignored; the loop keeps
  playing at the last tempo. The next MIDI Start restarts the loop from bar 1,
  so it lines up with the new pattern (Luca, 2026-10-22). Waiting actions stay waiting.
- **Stop HALT**: today's behaviour (Stop halts the loop, drops waiting actions,
  Start plays from bar 1).

## Firmware services

First GRDLOOP build (2026-10-22): only the cycle word ships (word 21, offset 84,
zero until Perform mode writes it). Items 1, 3 and 4 below have no user without
Perform mode, so they wait for the Perform build. The looper keeps its own grid
from the transport block.

1. **Press routing:** in Perform, a control aimed at FX4 Ftsw writes the looper's
   press counter, so the looper works without being under the cursor.
2. **Grid owner:** the firmware publishes bar 1, bar/beat position and the cycle
   length (Perform's CYCLE if set, else 0) in the services block; the looper reads
   them instead of keeping its own bar count.
3. **LED owner:** in Perform, `PERF_LED` drives the footswitch LED from the
   looper's state (table in the brief); outside Perform the looper's own PWM.
4. **Loop events:** Perform reads the looper's `ev_rec / ev_stop / ev_del`
   counters for the LOOPER menu rows.

## Cover and animation

The effect is renamed **GRDLOOP** (Luca, 2026-10-22). Cover (done in
`make_cover.py`): GRDLOOP in big letters on top, with the two Os fused into one wide rounded spiral as wide as GRD (25 x 13 px, 2 px lines, a pixel filled in each inner corner), no glitches, and under it Perform mode's top
bar as a long rounded bar, filled 5 of 8 bars, PLAY on the fill, 5.1/8 on the
right, a gap in the top and bottom edges at each bar line and a dotted line across the bar there (inverted under the fill, skipping text and the 1 px around it). Labels MIX / ROLL / SYNC.
Still to do in the build: effect name and file name GRDLOOP (manifest, build.py,
cover json), and the animation.

## Brief

Rewrite the brief's Looper section (still says Quant LOOP/BAR/OFF) from this
table, and point Perform's LOOPER menu at it.

## Work split (agent workflow)

| Step | Who | What |
|---|---|---|
| 1 | main | Services block layout (new fields), knob table above, merged into `docs/looper-services.md` |
| 2a | deep (Opus) | `looper.c`: Sync, Next/Cycle from the firmware grid, Stop KEEP/HALT, memory cap, old-patch mapping |
| 2b | Sonnet | Firmware: press routing, grid fields, LED owner, with tests in `tests/test_looper_patch.py` |
| 2c | quick (Haiku) | Mono (L+R)/2, cover labels, `make_cover.py` re-render, brief rewrite from this doc |
| 3 | quick | Build ZDL and firmware, test build to `CLAUDE` with test steps |

2a and 2b run in parallel once step 1 fixes the shared layout.

## Open

1. Animation: done (2026-10-23).
