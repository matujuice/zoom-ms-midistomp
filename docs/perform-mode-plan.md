# Perform mode: build plan

Status: building, 2026-10-22. Design: [v2.0-brief.md](v2.0-brief.md) Phase 3 and
[perform-ui-mockup.html](perform-ui-mockup.html) v14. Decisions and addresses:
[perform-mode-p0.md](perform-mode-p0.md), [perform-mode-p0-research.md](perform-mode-p0-research.md).
Shared interface: `asm/perform/perform.h`.

## Decided for the first build (Luca, 2026-10-22)

- Everything at once: play screen, SETUP, storage, LOOPER menu.
- Storage E: every move in 2 B (VALUE 7 bits, NEXT 5, LAG 4). One patch = 112 B
  (`PerfPatch`), 50 patches = 5.6 KB after the mixer table in record 50.
- Controls: knobs 1-3 (turn, press, hold), cursor ◄ ▼ ► (press, hold), footswitch
  (press, hold). Cursor ▲ always leaves. No double press (the looper keeps its own).
- MIDI CC on a target Perform is moving: Perform wins (the CC is ignored while a
  Perform lag runs on that target).
- Footswitch LED: the footswitch's target owns it (the looper's state, or that
  effect's on/off).
- Transport: MIDI Start / Stop and patch change cancel everything; tempo change
  recomputes. With no clock, bar 1 is the first footswitch press in Perform (until
  then, entering Perform).
- RAM: region 1 of the looper starts at `0xC010A000` (32 KB lent for good).

## Parts

| Part | Files | Who |
|---|---|---|
| Interface | `asm/perform/perform.h`, this plan | main |
| Engine: grid owner, moves (VALUE/NEXT/LAG, Follow), targets (mixer CC in the block, effect knobs try-lock + 16 ms fallback), Perform-wins stamp, LED owner, press routing, S_CYCLE, loop events | `asm/perform/perform_engine.c`, hooks | deep |
| Storage E in record 50, keyed like the mixer table | `asm/perform/perform_store.c`, `pages.c` r50 size | deep |
| Screen 11 hooks, MENU entry PERFORM MODE (ENTER / SETUP), ▲ leaves | `asm/mixer/mixer.S` or a new `asm/perform/*.S`, `patches/mixer-m2.yaml` | deep |
| Gestures (30 ms bounce, 150 ms turn guard, 1-detent wobble, 400 ms hold) and screen keys, play and SETUP | `asm/perform/perform_keys.c` | Sonnet |
| Play screen and SETUP pixels from the mockup | `asm/perform/perform_draw.c`, host preview PNGs | Sonnet |
| Build, tests, test build `ms70cdr-2.10-midistomp-2.0-perform1.exe` | `scripts/build_mixer_ui.py`, `tests/` | deep |

## Pedal test (Luca)

1. MENU > PERFORM MODE > ENTER shows the play screen; ▲ leaves.
2. SETUP: CYCLE, LOOPER, one row per control; set knob 2 → FX1 Mix, Press 80 NOW,
   Follow 30 1 BAR. STORE, power-cycle, it comes back.
3. In Perform: knob 2 press jumps, falls back on the next bar; the column blinks while waiting.
4. Footswitch → FX4 Ftsw with GRDLOOP: rec / play / stop land on the cycle line; LED
   blinks the countdown, pulses while recording, on while playing.
5. LOOPER REC END → MIX XFade B100 over 1 BAR.
6. A MIDI CC on that target is ignored while the lag runs.
