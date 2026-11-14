# Patch editor handover, 2026-11-14

For MODWERK's session, taking over `editor/` and branch `claude/sysex-editor`. Patch editor plan:
[parsed-sparking-spark.md plan](../../../../.claude/plans/parsed-sparking-spark.md) is not in this
repo (it's a local plan file) — ask Luca if you need the full phase breakdown; summary below.

## What's done

PR 64's plan (Luca, 2026-11-08: PERFORM setup, add/remove effects, edit every parameter, then a
UX pass) is substantially complete:
- PERFORM panel: CYCLE, looper on/off + 6 event targets, all 7 controls (K1-3, LEFT/DOWN/RIGHT,
  FTSW) with target picker and TURN/PRESS/HOLD gestures (VALUE/NEXT/LAG), matching
  `asm/perform/perform.h`. Round-trips through the existing 05 SysEx path.
- Add/remove effects: picker grouped by category (stock + pack effects), delete button per slot,
  COUNT/routing (byte 17 zones) kept in sync.
- Every parameter editable, including pack effects (named controls where known, raw P1-P9
  otherwise).
- Just landed (this commit, `7d937c9`): single `chainLcd` canvas now also hosts the Add-effect
  picker (was a separate `addLcd` canvas) — same merge pattern as the knob pages. The IN LCD page
  no longer shows a synthetic Mono/Stereo toggle (that's a pedal-wide setting, not patch data); IN
  and OUT now show their real pedal-matching knobs (`InLvl`/`Mastr`).

## In progress / just added, not pedal-tested

- **PERFORM "Even steps" ramp mode** (new firmware feature, `asm/perform/perform.h` bit 25,
  `asm/perform/perform_engine.c` `ramp_value()`): a move can now ramp with equal time per step
  (including the first and last) instead of the default round-to-nearest, which gives the two end
  steps only half the time of the interior ones. Compiled via `scripts/build_mixer_ui.py --write`
  into `patches/mixer-m2.yaml`. Editor-only control for now (checkbox next to Lag in the PERFORM
  move editor) — **no on-pedal UI** to toggle it yet; the 3-knob move-edit screen
  (`perform_draw.c`/`perform_keys.c`) has no obvious free slot for a 4th control, left as an open
  question.
- Built as a test firmware (`MIDISTOMP-evenlag-360F-Updater-Windows.exe`, identity tag `M2EL`,
  combining this branch + Even-steps + a borrowed 360F/SYSCLK5 overclock patch from another
  worktree, for test purposes only — the overclock patch is **not** part of this branch). Delivered
  to Luca; he said "we will test soon" — not yet flashed/verified on real hardware.
- Was driven by an "EDM build-and-drop" use case (GRDLOOP Roll + PERFORM LAG): LAG's ramp
  endpoint-squeeze meant a build only reached its last value in the final instant instead of
  holding it for its fair share of bars. Even-steps fixes that; confirmed against Luca's real-world
  report before implementing.

## Open bugs / gaps

- No on-pedal control for the new Even-steps bit (see above).
- LAG table itself is back to stock (16 values, unchanged) after several rounds of back-and-forth
  with Luca about adding bar granularity — he asked to fully revert that part; only the Even-steps
  bit is new.
- Phase 0 unknowns from the original plan (empty-slot encoding, byte 108-110 bit layout, name
  field width 10 vs 11 bytes, P4/P8 widths) — check `docs/dev/mixer-mode-m0.md` for what was
  confirmed vs still assumed; `editor/patch.js`'s `PARAM_BITS` may still be narrower than some
  effects' real bit width.
- Phase 4 (graphics/UX overhaul — mobile layout, keyboard/touch moves, undo granularity, one hex
  helper, mockup styling) not started.

## What Luca asked for next

1. Test the Even-steps + 360F build on real hardware ("we will test soon").
2. Then continue the patch editor work (his own words: "And then do the patch editor stuff" —
   already acted on with the two fixes in this commit; Phase 4 UX overhaul is likely next).

## How to test

- **Editor only (headless)**: `node editor/test-patch.js` for encode/decode round-trips. For UI,
  serve `editor/` (e.g. `py -m http.server 8737 --bind 127.0.0.1 --directory editor`) and drive it
  with a browser tool — set up PERFORM/add effects/edit params, confirm the LCD canvas updates.
- **Real pedal (Chrome + Web MIDI)**: open `editor/index.html` in the user's real Chrome (it needs
  Web MIDI, Claude's built-in browser pane can't reach a real MIDI device). "Read all patches"
  first. PERFORM requires the MST SysEx hello handshake, which only exists on `claude/sysex-editor`
  — **released/stock firmware won't show PERFORM** (confirmed: Luca's pedal was on stock
  MIDISTOMP v2.0.1, identity `M201`, which predates this). Needs a build from this branch (or the
  test `M2EL` build) actually flashed to test live.

## Standing rules (unchanged)

No commit/push/merge/release without Luca's explicit OK beyond what's already landed here. Never
commit Zoom firmware images, `.claude/`, or `CLAUDE.md`. `docs/dev/repo-refresh-plan.md` stays
uncommitted (don't `git add` it). Run `graphify update .` after code changes.
