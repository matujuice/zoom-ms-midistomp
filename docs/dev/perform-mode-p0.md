# Perform Mode P0: research scope (draft for Luca)

P0 is to Perform Mode what M0 was to the mixer: research only, no build. It ends with a
go / no-go per feature and the hook points. The design is Phase 3 of
[`v2.0-brief.md`](v2.0-brief.md).

## What already exists (MS-70CDR 2.10 OS)

| Piece | State | Where |
|---|---|---|
| MIDI clock, transport block (running, start counter, clocks, tempo) | ported, in every 2.0 build | `patches/midi-clock.yaml`, L2 `0x1181FF00`, `docs/dev/transport-block.md` |
| Looper services block (press counter, LED GPIO, claimant, status text, progress) | ported, not in the mixer builds | `patches/looper.yaml`, DDR `0xC00F3000`, `docs/dev/looper-services.md` |
| CC targets: effect knobs and on/off, ROUTE / MIX CC 85-101 | done | `midi-cc.yaml`, `mixer-m2.yaml` |
| Key events on a screen of our own, C screens built with TI cl6x | done (chain screen) | `asm/mixer/chain_keys.c`, `chain_draw.c` |
| Free code RAM | about 6.9 KB: `0xC0100520`-`0xC0102000` (the C section grew to 34,080 B; looper buffer above); m0-probe could be dropped from the release | `patches/mixer-m2.yaml` |
| Quantized actions, LED countdown (in an effect) | WIP Looper ZDL: When IMMED / BEAT / BAR / CYCLE (CYCLE = next Amount-bar line from bar 1), bar grid from the transport block (96-beat wraps, Start = bar 1, no clock = runs on the pedal's tempo), countdown blink whose rate doubles as the time left halves, LED by PWM through the services block | effects pack `src/custom/looper/looper.c` (branch `claude/epic-thompson-rggzx8`) |

## Questions P0 answers

1. **Raw input.** Do knobs 1-3 give per-detent turn events, and press / release (not
   just "pressed")? Same for down / left / right and the footswitch. Without release
   times there is no hold or double. Find the input poll and its event numbers, and
   whether it is fast enough for a 30 ms debounce and 300 ms double.
2. **One place to run moves.** A tick that runs every audio block (the mixer engine or the
   transport poll) where a scheduled move is applied: CC value now, at the next clock
   step / bar, or after N loop cycles. Must not hold a DSP lock or call UI code.
3. **Applying a target from that tick.** Can the existing CC path (`midi-cc`, mixer CCs)
   be called from the audio side, or does it touch the screen and must be deferred to the
   16 ms poll? Lag (a ramp) needs repeated writes: what does a knob write cost?
   The looper's When / grid code is the model: P0 checks whether it can move to the
   firmware side as is (it reads the transport block, which the firmware also owns).
4. **Clock on 70CDR** (Luca: likely fine). Re-check the transport block fields on this OS: tempo with no MIDI
   clock (the pedal's own TAP / tempo), Start / Stop, and what a patch change does.
5. **Looper as a When source** (Luca: likely yes). Cycle N needs the loop length and position: are they in the
   services block (progress yes, cycle counter?). Perform with the looper means the looper
   patch goes into the 2.0 build: check room and conflicts with the mixer.
6. **LED countdown** (Luca: yes). Reuse the looper's PWM path through the services block;
   check the LED task doesn't fight it when the looper isn't under the cursor.
7. **Storage.** About 600 B per patch, 30 KB for 50. Record 50 already grew to 824 B. Where
   can 30 KB live in flash: a bigger record, a new record, a file in the effects FS (17
   free blocks), or fewer bytes (assign only what is used, e.g. 8 controls x 8 B)? This is
   the most likely no-go and decides the data format.
8. **Screens.** PERFORM and PERFORM SETUP as two new screens written in C, like the chain
   screen: menu entries, the up button always leaving, combos and HOLD FOR off inside.
   P0 only finds the hook points. The design comes after P0 as UX/UI mockups, like the
   mixer's (`mixer-ui-mockup.html`).

## Results (2026-10-22, static research, nothing run on the pedal)

Details and addresses: [perform-mode-p0-research.md](perform-mode-p0-research.md).

| # | Verdict | In short |
|---|---|---|
| 1 Raw input | go, probe 2 numbers | Every key and knob push arrives at a screen as press and release events (64-75, footswitch 32/33, knob 1 push 34/35), already debounced by the OS. Turns arrive as events 160-162 with the step count, at most one per knob per 16 ms. No stock hold or double: we time them ourselves in the 16 ms poll. Probe: counts per detent, tick length |
| 2 Moves tick | go | Top of `engine_run` (once per audio block, interrupts off, no locks). The looper's grid / When code moves over almost line for line; the firmware becomes the grid owner and counts beats and bars from the transport block every block, looper loaded or not. About 0.5-1.5 % of a block |
| 3 Targets | mixer go, effect knobs needs probe | Mixer CC 85-101: one byte in LIVE, same block, already smoothed. Effect knobs / on/off: stock calls hold a lock; plan = skip when busy, 1-2 writes per block, fallback through the 16 ms poll (up to 16 ms late). Probe: cost and safety per effect type |
| 4 Clock | go | Transport block valid on 70CDR; with no MIDI clock it carries the patch / TAP tempo. Start resets the bar; a patch change keeps the grid but may change the tempo (TEMPO LOCK) |
| 5 Looper cycles | go, optional | Perform is its own world: its beat / bar grid runs in the firmware (row 2) with or without the looper. The looper only adds the CYCLE When; with no looper loaded that choice is hidden. The looper publishes state, length and a cycle counter in 4 free services words. `looper.yaml` + mixer: one shared hook (poll trampoline `0xC00C82D0`), chain mixer through the looper's `poll_pre` |
| 6 LED | go | Each block, copy the LED task's desired bit into its applied bit (it then never writes) and drive the GPIO ourselves; a PERF_LED owner word in the services block |
| 7 Storage | 30 KB no-go, compact go | Up to 64 B per patch (3.2 KB) in record 50 next to the mixer table: only assigned controls are stored |
| 8 Screens | go | One screen, id 11 (the only free slot: key `0xC00EEFC8`, draw `0xC00EEBDC`), sub-mode PERFORM / SETUP; MENU entry 7 → PERFORM. Combos and HOLD FOR only exist in play mode, so they are already off there; UP reaches the screen |

**Constraints found:** free code RAM is about 6.9 KB; dropping m0-probe from the release frees
about 12 KB. 64 B per patch shapes the design: a fixed list of assigned controls, not every
gesture of every control.

## Brief vs P0: decisions (Luca, 2026-10-22)

| # | Topic | Decision / proposal |
|---|---|---|
| - | Gestures | Double press only on the footswitch (Luca). Knob: turn, press, hold = 6 moves; button: press, hold = 5; footswitch: press, double, hold = 7. Total 40 moves per patch. One target per control; the footswitch's gestures and follows may each have their own |
| 1 | Storage | **Proposal E:** every move in 2 B: value 7 bits, When 5 bits, Lag 4 bits (lists below). 40 × 2 B + ~12 B targets ≈ 96 B/patch, 4.8 KB for 50, in record 50 (R50 ≈ 5.6 KB, RAM 2 × 5.6 KB, fits once m0-probe is out; compaction about every 20 STOREs, time to probe). Older text below: goal every control and gesture assignable with moves. Full set ≈ 52 moves × 3 B + targets ≈ 170-192 B/patch, 9.6 KB for 50. Options below; **open** |
| 2 | Bar 1 with no MIDI clock | Proposal: the first footswitch press in Perform (as the looper WIP does); until then the grid runs from entering Perform. MIDI Start always sets bar 1. Firmware owns the grid and publishes it; the looper reads it |
| 3 | Patch change | Grid keeps running. Pending moves and follows of the old patch are cancelled (their targets belong to it). The loop lives in the patch, so it goes with it |
| 3 | Footswitch | A control like the others: its target is the looper, an effect's on/off or any CC, plus moves per gesture. Default in a patch with a looper: LOOP. New command word in the services block: Perform decides gesture and grid line, the looper executes `REC / STOP / PLAY / DELETE / ROLL n` in the same block. Outside Perform the looper keeps its own press logic |
| 5 | Type target | Dropped: changing an effect's type loads another effect, not possible from the audio side |
| 6 | MIDI CC on a Perform target | External CC wins: it stops a lag in progress on that target; follows already scheduled still fire later. Needs a "target written" stamp in the CC path |
| 7 | Saving | Assignments per patch. Moved values are normal effect / mixer values, saved by STORE / AUTO SAVE |
| 8 | Looper event → mixer | Yes; probe the same-block timing |
| 9 | Code RAM | Superseded: see "Where the RAM comes from" below (borrow from the looper now, drop m0-probe at release). Earlier note: drop `m0-probe.yaml` from the Perform builds and the release: frees `0xC00F3100`-`0xC00F6000` (12 KB, contiguous) → about 19 KB free plus ~4 KB in small gaps. Keep from the probe, as a tiny patch: the DSP limit 300 (`0xC00BB52C`). Also compile the UI C files for size (cl6x `-ms`, engine.c stays `-O2`), estimate 20-30 % off the 34 KB, to measure. Enough for Perform code with storage A or D; storage B needs ~20 KB of record buffers and would not fit |
| 10 | Moves at once | 7 controls (+ footswitch gesture targets); each can have a lag running and a follow waiting: 16 slots, ~0.4 KB |
| - | Knob turn step | Stock step |
| - | After leaving | Footswitch and LED back to stock; pending follows keep running |
| - | MIDI Stop | Proposal: grid stops, pending grid moves are cancelled, the loop keeps playing; MIDI Start = bar 1 and the loop jumps back to its beginning (Luca) |

**Moves (Luca, 2026-10-22):** a Turn has only a Follow; Press has Action + Follow; Hold has Action + Release + Follow. Every move has Value (0-127), When and Lag. A move fires once, nothing repeats.

- **When** (20 of 32): immediately · 1, 2, 4, 8 beats · 1, 2, 4, 8, 16, 32 bars · 1, 2, 4, 8, 16, 32 cycles · on loop recorded / stopped / deleted. Action and Release read it as "next X" (the next X line of the grid, bars from bar 1); Follow reads it as "after X" (counted from when the Action landed). Cycles belong to Perform (Loopy Pro's master cycle): the cycle length (bars) is set per patch in PERFORM SETUP and counts from bar 1, looper or not. The looper adapts: a setting OWN (length set by the footswitch, snapped to whole bars, on the grid) or SLAVE (records from the next cycle line for one cycle, then stops by itself). With no clock running, quantized moves fire at once (as in Loopy Pro).
- **Lag** (16 of 16): off · micro (the shortest ramp with no click: found by ear in the probe, typically 2-10 ms) · 50, 100, 500 ms · 1 s · 1, 2, 4, 8 beats · 1, 2, 4, 8, 16, 32 bars.

**RAM for storage (Luca: keep it stock style):** the Perform table goes in record 50 next to the mixer table and is loaded and saved exactly as the mixer table is today (whole record image in RAM + cleanup buffer, ~11 KB). No new save scheme. If RAM runs short: drop some moves, or take RAM elsewhere (below).

**Where the RAM comes from (Luca):** keep m0-probe in the test builds (still needed). During development, borrow 32 KB from the looper: region 1 starts at `0xC010A000` instead of `0xC0102000` (`asm/looper/block.S` row + the constants in tests and `build_mixer_ui.py`), costing the looper ~0.25 s. Update (Luca): that is fine for good; m0-probe stays. The looper's floor is **8 bars stereo from 100 BPM up** = 19.2 s (about 2.6 MB of its ~3.4 MB), so up to ~800 KB could be lent if ever needed.

**Looper length (Luca):** 8 bars at 40-240 BPM. The buffer gives 25.4 s stereo / 49.7 s mono; 8 bars at 40 BPM = 48 s, so below about 76 BPM it records mono or stereo at half rate. The looper buffer is not reduced.

**Decided later (Luca, 2026-10-22):** no Double gesture (footswitch: press, hold; the looper keeps its own double press delete), so 37 moves per patch, not 40. A Follow lands exactly its NEXT after its Action or Release landed; a Turn's Follow waits for the next line. MENU order: EFFECT CHAIN, DELETE EFFECT UNIT, PERFORM MODE (opens ENTER / SETUP), SETTINGS, MIDI SETTINGS, VERSION.

**Transport rules (Luca, 2026-10-22; replaces the MIDI Stop proposal above):**
- **MIDI Start or Stop:** resets Perform. Every pending move and Follow is cancelled, lags in progress stop where they are, and the grid restarts at bar 1 (Start) or stops (Stop). Quantized moves fire at once while no clock runs.
- **Patch change:** resets the same way; the new patch's assignments load.
- **Tempo change:** nothing is cancelled. Beat, bar and cycle lines, lags in beats or bars and the countdown blink are recomputed from the new tempo; a move keeps its grid line, not its time in ms.

**Decided (Luca, 2026-10-22, before the build):**
- Storage: **E** (every move, 2 B; record 50 next to the mixer table).
- First build: **everything at once** (play screen, SETUP, storage, LOOPER menu).
- MIDI CC on a target Perform is moving: **Perform wins**; the CC is ignored while a Perform move lags on that target. Replaces row 6 above.
- Footswitch LED in Perform: **the footswitch's target owns it.** Aimed at the looper (FX4 Ftsw) it is the looper's LED (countdown blink, pulse, on); aimed at an effect's on/off it shows that on/off.

**Storage options (1):**
- **A. Cap 64 B/patch:** any control assignable, about 20 moves per patch. Smallest, fits record 50 as planned.
- **B. Full per patch (~192 B) in record 50:** R50 ≈ 10 KB, written on every STORE (the mixer table is there too). A full flash bank then compacts about every 12 STOREs (140 KiB erase + copy, time unmeasured: probe).
- **C. Full per patch in a new record 52,** written only when Setup changes. Fewer flash writes, but it changes the record store that holds all patches (riskier).
- **D. Perform sets:** ~10 global sets of ~192 B (2 KB), each patch stores a set number. Small, but a set is shared by every patch using it (targets are by position).

**Next:** a P0 probe build (counts per detent, tick length, events on screen 11, effect knob
writes from the audio block: cycles and safety per effect type), then the UX/UI mockups.

## Deliverables

- `docs/dev/perform-mode-p0.md` filled in: answers, addresses with confidence, go / no-go.
- A Perform plan (`docs/dev/perform-mode-plan.md`, like the mixer plan) with steps P1... and
  what Luca hears at each.
- No firmware change. A probe build only if a question can't be answered statically
  (for example measuring input event timing), as M0 did.

## Who does what

- Questions 1-4 and 6: Opus (OS reverse engineering, timing).
- Questions 5 and 7: Sonnet reads the existing docs and record store code, Opus checks.
- Question 8 and the plan: main session with Luca.
