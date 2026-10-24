# Perform Mode P0: research notes (MS-70CDR 2.10)

Three static research passes, 2026-10-22 (dis6x of the 2.10 OS, repo docs and sources; nothing run on the pedal). Summary and verdicts: [perform-mode-p0.md](perform-mode-p0.md). Free code RAM is about 6.9 KB (`0xC0100520`-`0xC0102000`), not the 21 KB some notes below assumed from the M3b docs.

## P0 Perform Mode: raw input (Q1) and new screens (Q8). MS-70CDR 2.10

How this was found: I extracted the OS image from the updater (scratchpad parts/), wrapped it in an ELF with the C674X ISA attribute (scratchpad mkelf.py) and ran a full dis6x disassembly (scratchpad os.dis, 110k lines). I then read the repo docs and patches (mixer-m2.yaml, midi-settings.yaml, tempo-hold.yaml, asm/mixer/*, asm/tempo_hold/hold.inc). The repo itself was not touched.
B14 = 0xC00EF748. MODE = B14[80], SCREEN = B14[88]. The UI key mailbox is B14[202].

### Q1: raw input

### Answer
There are two scanners and one encoder ISR. They all post into the same UI mailbox B14[202], through 0xC00DA840.

1. **The 16 ms task** (Task_SwitchNrmlSpdRead loop at 0xC00C6980). It covers 7 switches and the 3 knob turns.
   - Raw switch word: 0xC009DF8C, built by 0xC00CD474 from GPIO, 7 bits.
   - Debounced word: 0xC009DF90 = old raw & new raw. A change must be stable for 2 polls, so it lands 16-32 ms after the edge.
   - The mask table at 0xC00EC850 (1, 2, 4 … 0x40) drives the post loop at 0xC00C69F8-0xC00C6A48. Bit i posts event 64+2i on press and 65+2i on release.
   - Bit to event map:

     | Bit | Control | Press / release |
     |---|---|---|
     | 0 | knob 2 push | 64 / 65 |
     | 1 | knob 3 push | 66 / 67 |
     | 2 | UP / type + | 68 / 69 |
     | 3 | DOWN / type − | 70 / 71 |
     | 4 | LEFT | 72 / 73 |
     | 5 | RIGHT | 74 / 75 |
     | 6 | unknown, maybe not wired | 76 / 77 |

   - Turns: for each knob k in 0..2, if the encoder count 0x1181DE70[k] is nonzero (getter 0xC00D8EEC), it posts event 160+k (0xC00D8E40 → KEY_POST). So turns are coalesced to at most 1 event per knob per 16 ms.
   - After that it runs the 100 ms housekeeping, then sleeps for whatever is left of 16 ms (sleep 0xC00CEBC0, ticks 0xC00DEE20, 0xC00C6B24-0xC00C6B44).
   - Our existing poll hook site is 0xC00C6998 (poll.S / mixer poll / chain_poll).

2. **The 1 ms Clock-tick scanner** (0xC00C6B48). It covers the footswitch and knob 1 push.
   - Call path: tick function 0x1181A820 (pointer at data 0xC00F0D74) → call at 0x1181A838 → L2 trampoline 0x1181A950 → 0xC00C6B48.
   - It is enabled by byte B14[548], which init 0xC00C6CCC sets to 1 (called at 0xC00AB624).
   - Raw word: 0xC009DF7C (read by 0xC00CD52C). Masks at 0xC00ECD48 are 1 and 2.
   - Bit 0 = footswitch (32 press / 33 release). Bit 1 = knob 1 push (34 / 35).
   - A change is accepted only if more than 19 ticks have passed since the last accepted change of that switch (timestamps at 0xC009DF74[i]). That is a ~20 ms lockout, not a stability check.
   - Other state words: 0xC009DF80, 84 and 88 (not decoded).

3. **The encoder ISR** (L2 0x11819EB4, GPIO bank interrupt, INT7). It is interrupt-driven, separate from both pollers.
   - Pin table 0x1181DE40 (address/mask pairs per knob and phase). Phase state bits at 0x1181DE80[k].
   - It adds ±1 per decoded edge into 0x1181DE70[k] (via 0x1181A720).
   - How many counts one detent makes (1, 2 or 4) is not known.

**What a screen's key handler receives** (UI receive 0xC00D1418):

| Event | Steps (A5) |
|---|---|
| 160-162 (turns) | 0x1181DE70[ev-160], read and then cleared by 0xC00D8F10. If the count is 0, the event becomes 0xFFFF and is dropped. Positive = clockwise. |
| 32-35, 64-77, 256 | 1 |

- So the handler gets press and release for all 9 switches, plus turns with a signed step count.
- The OS has no built-in hold or double-press. "Hold" is a 1 s timer: 0xC00C7C80(timer, on) posts 224+n. Event 227 = knob 3 hold, 228/229 = type hold, 230/231 = cursor hold, 232/233 = AUTO SAVE.
- Only the stock play-mode handlers start those timers. In MODE 11 nothing starts them unless our screen does.
- All 3 encoder counters are cleared by 0xC00D8F30 (called from 0xC00D1518). Init is 0xC00D8E60 (from 0xC00D4320).

**Raw state we can read for our own recognizer**

| What | Address | Getter | Notes |
|---|---|---|---|
| 7 switches | 0xC009DF8C (raw), 0xC009DF90 (debounced) | 0xC00C6D84(mask), returns 1 = down (bit clear) | |
| Footswitch, knob 1 | 0xC009DF7C | 0xC00C6DA4(mask), returns 1 = down | |
| Encoder counts | 0x1181DE70[0..2] | | Signed accumulators. The UI consumes and clears them on each 160-162 event, so do not read-and-clear them from a poll (race). Use the event steps (A5) instead. |

**Recommended recognizer design (P0)**
- Run it on events in the screen key handler, plus a time base from the 16 ms poll we already have (chain_poll pattern).
- Time base: getTicks 0xC00DEE20 (1 tick ≈ 1 ms; needs probe).
- Spec values against the hardware:
  - **30 ms debounce:** the OS already gives 16-32 ms (2-poll AND) or a 20 ms lockout. Do not add a second debounce.
  - **150 ms turn lockout, 400 ms hold, 300 ms double:** all fine at 16 ms granularity. Do them in our code, timestamping each press and release event with getTicks.
  - **Hold:** check "down for more than 400 ms" in our 16 ms poll, using the press timestamp and the raw getters above. Do not use the stock 1 s timers.
- Footswitch and knob 1 come from the 1 ms scanner, so their timing is finer. There is no need to hook the tick.

**Combos and HOLD FOR**
- Footswitch press is handled at 0xC00AC990. The HOLD FOR getter 0xC00BA3B8 is called at 0xC00ACAB8 (press) and 0xC00AC920 (release). HOLD_WORD is 0xC009D920.
- Our tempo-hold hooks: hold.S (L2 0x1181FA80), hold2.S (0x1181FF20), the combo cave 0xC00D4090, and toggle_hook / swallow_hook / release_hook. combo_hook acts on events 228-231.
- All of this runs only in play mode (MODE 0). The main UI loop 0xC00ACDB0 sends events to the screen dispatcher 0xC00A82AC when MODE = 11 (call at 0xC00AD1EC).
- So a MODE 11 screen (like the chain screen) already gets raw events with no combos and no HOLD FOR. Perform screens need no new disable switch, as long as they live in MODE 11.
- **The up button reaches the screen handler:** in MODE 11, UP = event 68/69 is passed to the screen's key function. The brief's rule "up always leaves" is then just our handler calling the return path (the row -2 "our own return" pattern from chain_keys.c).
- Open: 0xC00CCC50, which the docs list as a pre-filter for 225-231, looks from the disassembly like a timer start/stop helper (it stores into 0xC008DFA8[n] and calls 0xC00D39F0 / 0xC00BB160). I did not confirm what it does with 225-231 in MODE 11. It only matters if we use those timer events, and P0 should not.

### Addresses and confidence
| What | Address | Conf. | How |
|---|---|---|---|
| 16 ms switch task loop | 0xC00C6980 (hook 0xC00C6998) | high | disasm + existing poll.S hook |
| Raw / debounced 7-switch words | 0xC009DF8C / 0xC009DF90 | high | disasm |
| Switch post loop, mask table | 0xC00C69F8-6A48, 0xC00EC850 | high | disasm + table read |
| Turn post | 0xC00D8EEC (get), 0xC00D8E40 (post 160+k) | high | disasm |
| UI receive, step count | 0xC00D1418, clear 0xC00D8F10 | high | disasm |
| Encoder ISR, counters | 0x11819EB4, 0x1181DE70[3] | high (role), low (counts per detent) | disasm |
| 1 ms footswitch / knob 1 scanner | 0xC00C6B48, raw 0xC009DF7C, 20-tick lockout | high | disasm |
| Tick function | 0x1181A820 (ptr 0xC00F0D74) | medium (period 1 ms assumed) | disasm; the "ticks = ms" claim comes from sleep(16) use |
| Down getters | 0xC00C6D84, 0xC00C6DA4 | high | disasm |
| Hold timers | 0xC00C7C80 → 224+n after 1 s | medium | docs + hold.inc |
| MODE 11 skips combos / HOLD FOR | dispatcher call 0xC00AD1EC | high | docs (mixer M3 research) + chain screen behaviour on hardware |
| Bit 6 (76/77) wired? | n/a | low | unknown |

### Open points
- Counts per detent (1, 2 or 4). Does fast turning give A5 > 1 per event? It should, because of the coalescing.
- The real tick period. Is 1 tick = 1 ms?
- Is bit 6 (events 76/77) wired to anything?
- Is there a stock "turn while pressed" behaviour? Not seen; the OS posts turns and pushes independently.

### Verdict Q1: **GO, needs probe** (detent scale and tick period only).

### Q8: two new C screens (PERFORM, PERFORM SETUP)

### Answer
**Free screen ids.** These come from the key table 0xC00EEFA0 (ids 1-17) and the draw table 0xC00EEBB4.

| Id | State | Used by |
|---|---|---|
| 1 | ours | settings / PEDAL INPUT (mixer-m2 overwrites the midi-settings entry) |
| 3 | ours | Effect Chain (mixer-m2 M3b) |
| 11 | **free**: stock default key 0xC00A8310, draw 0xC00A9398 | |
| 13, 14 | ours | midi-settings |
| 15 | ours | MIXER (mixer-m2) |
| 16, 17 | stock | real handlers 0xC00A8342 / 0xC00A8338 |
| 32-34 | stock | handled outside the 1-17 table |

The dispatcher bound is `SCREEN-1 <= 16`, so ids 18+ would need a dispatcher patch.

**Plan: one screen id (11) with a sub-mode word: 0 = PERFORM, 1 = PERFORM SETUP.**
- Patch two table words, the same way mixer-m2 does for screen 3:
  - key entry 0xC00EEFC8 (expect `10830ac0`) → our perf_key vector
  - draw entry 0xC00EEBDC (expect `98930ac0`) → our perf_draw vector
  - Both expect values were read from the image (zoomms.ais) and match the stock default handlers.
- Put the code in the existing C area: chain_vec.asm vectors + C at 0xC00F8000. The C code currently ends at 0xC00FCC40, and free code RAM runs to 0xC0102000, which leaves about 21 KB.
- Add vectors to chain_vec.asm and build them with the existing scripts/build_mixer_ui.py flow.
- Store the sub-mode in our own RAM next to the chain screen state, not in B14.
- Getting a second real id would mean patching the dispatcher's bound check plus extending both tables, which are in the stock data area with no room after them. That is not worth it for P0.

**Menu entry**
- Our settings menu currently has 6 entries (mixer-m2): menu_draw.S at 0x1181EF78 (MENU6 count), menu_scroll.S at 0x1181F0B0 (scroll limit, `5aa31802` = 6), and menu_enter.S at 0x1181F0F0.
- menu_enter maps entry → screen as `add 11, a3, a4` (3→14, 4→15), with 5 → screen 9 (version). A SET_SCREEN(A4, B4 = row 0) then follows.
- Adding PERFORM as entry 6 means:
  - the count goes to 7 in menu_draw.S and menu_scroll.S;
  - one more name string;
  - in menu_enter.S, entry 6 → screen 11 (one more cmpeq / mvk pair; the 8-instruction block has 2 nops free);
  - set the sub-mode to 0 before SET_SCREEN.
- PERFORM SETUP is reached from inside PERFORM (a key gesture flips the sub-mode and redraws), so it needs no menu entry.
- Alternative: no menu entry at all. Enter PERFORM from a play-mode gesture by calling SET_SCREEN 0xC00A75E0(11, 0) with MODE = 11, the same as any screen enter. This is decided in the design, not here.

**Hooking like the chain screen**
- Key handler: vector → C perf_key(ev, steps).
- Draw handler: vector → C perf_draw().
- Exit: the row -2 "own return" convention / SET_SCREEN back to play.
- Periodic work: add a `if (SCREEN == 11) perf_poll();` branch to the existing mixer.S 16 ms poll, which is where chain_poll already runs.
- chain_poll starts and stops TIMER6 / TIMER7 in MODE 11. perf_poll must not collide with that. Both screens can never be active at once, but the stop on screen exit must run.
- The edited mark / AUTO SAVE (0xC00ACD84) runs after every event, in every mode. Perform must not mark the patch dirty unless that is intended.

### Addresses and confidence
| What | Address | Conf. | How |
|---|---|---|---|
| Key table, draw table | 0xC00EEFA0, 0xC00EEBB4 (id n at +4(n-1)) | high | table read + mixer-m2.yaml / midi-settings.yaml |
| Id 11 free (default handler) | 0xC00EEFC8 = 0xC00A8310, 0xC00EEBDC = 0xC00A9398 | high | table read; no repo patch writes them (grep of patches/) |
| Dispatcher, bound check | 0xC00A82AC, `SCREEN-1 <= 16` | high | disasm |
| SET_SCREEN | 0xC00A75E0 | high | docs + existing use |
| Menu draw / scroll / enter hooks | 0x1181EF78 / 0x1181F0B0 / 0x1181F0F0 | high | mixer-m2.yaml + menu_enter.S |
| Free C code space | 0xC00FCC40-0xC0102000 | medium | docs (mixer M3b); re-check the map after the last build |
| Chain poll site (16 ms) | mixer.S poll via 0xC00C82D0 trampoline | high | mixer-m2.yaml |

### Open points
- Does stock code ever SET_SCREEN to id 11 by itself? Not searched exhaustively; a probe should confirm nothing else lands on 11.
- Expect bytes verified: 0xC00EEFC8 = 10830ac0, 0xC00EEBDC = 98930ac0; no repo patch writes either.
- Mac and other models: only the 70CDR 2.10 was checked.

### Verdict Q8: **GO.** Screen id 11 plus a sub-mode word, hooked like the chain screen; menu entry 6 through our own menu code.

### What a probe build needs to measure
1. **Counts per detent.** Log A5 for event 160-162 on slow single-detent turns (expect 1, 2 or 4), and the maximum A5 on fast spins.
2. **Tick period.** Log getTicks (0xC00DEE20) deltas between consecutive 16 ms poll calls, and over a 10 s wall-clock window.
3. **Event latency.** Timestamp the press and release events (64-75, 32-35) against the raw words DF8C / DF7C changing. This confirms the 16-32 ms and 20 ms figures and the press-to-event time for the 300 ms double press.
4. **Bit 6.** Does event 76/77 ever fire, and does DF8C bit 6 ever change?
5. **Events 224-233 in MODE 11** while screen 11 is up. Does anything (0xC00CCC50 included) post or swallow them? Expect none.
6. **Screen 11 is free.** Set the screen 11 table entries to a logging stub, walk all stock menus and screens, and confirm the stub never runs unless we enter it.
7. **Turn while held.** Hold knob 2/3 push and turn: confirm both press and turn events arrive (needed if Perform uses push-turn gestures).
8. **No dirty mark.** In screen 11, check that key handling does not set the edited mark / trigger AUTO SAVE (0xC00ACD84 path).

## P0 research: scheduled moves, CC from audio, LED countdown (Q2, Q3, Q6)

Target: MS-70CDR OS 2.10, C6740 at 300 MHz. One audio block is 8 frames and has 54,422 cycles.
Sources:
- my own disassembly of the OS image (scratchpad m3a/all.txt);
- the repo files asm/mixer/{engine.c,mixer.S}, asm/midi_cc/handler.S, asm/looper/looper.S;
- zoom-ms-zdl-effects-pack/src/custom/looper/looper.c and zmt.h.

Summary:
- Q2: GO.
- Q3: mixer GO; effect knobs NEEDS-PROBE.
- Q6: GO.

---

### Q2. Which per-block hook applies a scheduled move?

### Answer
Use the mixer engine (engine_run in asm/mixer/engine.c). It is the only code the firmware owns that runs once per audio block.
- mixer.S `engine` is vector +0. It replaces the stock slot loop at 0x1181BE00.
- That loop is called from the L2 call list at 0x1181BDE0.
- Before the chain, the pre-chain step 0x1181AFA0 turns interrupts off.
- So the move code runs atomically with respect to every task: no locks are needed against the UI, MIDI or LED tasks. It must still never block or call UI code.

Add a `moves_tick()` call at the top of engine_run, before the gains are smoothed, so a move applied in this block is heard in this block.

The other hooks are not per block:
- poll.S runs in Task_SwitchNrmlSpdRead every 16 ms.
- clock.S runs once per MIDI byte, in Task_MIDI.

Both stay useful as producers: they parse input, queue moves and redraw. They are not the place to fire moves.

### Can the looper's When/grid logic be moved over as it is?
Yes, almost line for line. looper.c already does the right thing per block:
- Grid position: gu is in units of 1/8 beat, gf is the fraction.
- lp_next(u, m) = u - u%m + m.
- When values: BEAT m=8, BAR m=32, CYCLE m=amt<<5, IMMED.
- MIDI Start re-aims: gu = -1, gf = 0.999, and pending moves are re-aimed to 0.
- With no running clock, it free-runs at du = bpm * 3.0234014e-6 units per sample.
- zmt.h zt_update reads the transport block at L2 0x1181FF00:
  - magic 0x5A4D5401, seq retry, run flag, start counter;
  - clocks since Start (24 per beat), BPM x 100;
  - interpolates between clocks and wraps at 2304 clocks.
  - It uses plain loads and no locks, so it is already audio-safe.

Port as is: zt_update, the gu/gf advance, lp_next, and the Start / Stop / patch-change reset.
New part: a small move queue. Each entry holds target, value, due unit, Lag and an id. The newest move on a target replaces the older one, which follows the brief's "newest wins" rule.

### Placement and constraints
- Code goes in DDR C, in the free area 0xC00FCC40-0xC0102000 (about 21 KB) or next to the mixer C code. The hot path is small, so L1P caches it after the first block.
- State: grid about 100 B, plus a queue of 16 moves x 16 B = 256 B. Put it in DDR next to MIXER_BASE 0xC00F6000. It does not need to be in L2: it is a few words per block.
- No UI calls, no Semaphore_pend, no Task_sleep, no flash access. The audio side only sets a "redraw" bit; the 16 ms poll does the screen and edited-mark work (see Q3).

### CPU / RAM
- Grid update: about 100-200 cycles.
- Queue scan of 16 entries: about 100-300 cycles.
- Applying a mixer move: about 10 cycles.
- Total: about 300-800 cycles per block, which is 0.5-1.5 % of a block.
- RAM: about 0.4 KB data and about 1.5-2.5 KB code.

### Confidence
- Engine is the only per-block hook, called from 0x1181BDE0: high (repo code plus disassembly).
- Interrupts off around the chain (0x1181AFA0): high.
- Whether the audio context is an HWI or a task: medium. I found no caller of 0x1181BDE0; there is only an unaligned word hit at 0xC00F06CD. This does not matter while interrupts are off.
- The looper grid ports cleanly: high (it is already C that runs per block).

### Open points
- The engine only runs in builds that install the mixer hook. If Perform must work without the mixer, it needs its own small slot-loop replacement or a call-list entry.
- Avoid two grids. Let the firmware own gu/gf, publish them next to the transport block, and have the looper ZDL read them later. Until then both compute from the same transport block, so they agree within one block.
- With no clock and no looper, the Cycle choice stays hidden (as the brief says). Free-running BEAT/BAR uses the patch BPM.

### Verdict: GO

---

### Q3. Can the effect-knob, on/off and mixer CC paths run from audio?

### 3a. Mixer CC 85-101
mixer.S `cc` does three things:
1. Scales the value: v' = (v*max + 63)*259 >> 15.
2. Stores it in LIVE[s] at MIXER_BASE+224 (it also mirrors INR / MR).
3. Calls UI_REFRESH 0xC00ACD84 (sets the edited mark, re-arms the AUTO SAVE timer) and Event_post 0xC00CBF40(B14[656], 0x40) to redraw.

engine_run reads LIVE[] every block and smooths with g += (t-g)/4, so the change is already declicked.

From audio:
- Store the LIVE byte directly: about 10 cycles, block-exact.
- Set a dirty flag. The 16 ms poll then calls UI_REFRESH and Event_post.
- Decide whether a move should mark the patch edited at all. Probably not, because a move is a performance gesture. In that case skip UI_REFRESH and only post the redraw.

Confidence: high. Verdict: GO.

### 3b. Effect knob / on/off (midi_cc handler.S)
The current CC path:
1. Max value = FX_PARAM_DESC 0xC00B056C(slot, param) word +12.
2. SEM_PEND 0xC00C7EE0(B14[191], -1).
3. FX_SET_PARAM 0xC00BB600(slot, param, value, B6=0, A8=1).
4. SEM_POST 0xC00D6B00.
5. UI_REFRESH 0xC00ACD84.
6. EVENT_POST(B14[656], 0x40).

Every stock caller of 0xC00BB600 holds B14[191] around the call:
- 0xC00ABB2C, 0xC00ABCF8, 0xC00ABD10;
- 0xC00AEC20, 0xC00AEC44;
- 0xC00BB8C0, 0xC00BB910.

So B14[191] is the effect-edit lock. A blocking pend is not allowed on the audio side, so this path cannot be called from audio as it stands.

What fx_set_param does with B6=0 (disassembled, high confidence):
1. Calls 0xC00B056C(slot, i) up to 11 times to count the params (descriptor word 11, bit 2).
2. Rejects a param past the count and clamps the value to the descriptor max (+12).
3. Returns early if the value equals the patch word at 0xC009BF58 + 44*slot + 4*param.
4. Param 1 (effect type) goes to 0xC00BB490 and the DSP check 0xC00BB544. Never touch param 1 from audio.
5. Other params: stores into the patch word, then calls 0xC00BB284. That function:
   - stores the same value into a second copy at 0xC009C1A0 + 44*slot + 4*param;
   - if the slot is not DSP-off (mask at 0xC009C060), jumps to the effect's own edit callback desc(slot, param)[7], with A4 = state from 0xC00C8E6C(slot). This is the effect's own coefficient update.
6. With B6=0 it skips 0xC00AF0A4 and 0xC00AE634, which are the notify / UI side.
7. So it makes no screen calls, no flash writes and no pends. The patch is marked edited later, when IS_DIRTY 0xC00B8534 compares the two patch copies.

### Plan for calling it from audio (try-lock, never block)
1. Skip the write and retry next block when either:
   - the B14[191] semaphore count is 0 (a task holds it), or
   - a patch load or effect swap is running (B14[98] / FX_TABLE entry 0xC00E0784, the same checks the CC path uses).
   Interrupts are off during the chain, so a task cannot take the lock while we run. Reading the count is enough; no post/pend is needed.
2. Pre-check the patch word at 0xC009BF58 + 44*slot + 4*param. If it already equals the value, skip the call. This avoids the 11-call count loop.
3. Call 0xC00BB600(slot, param, value, 0, 1) for params 0 and 2-9 only. On/off is param 0.
4. Set the dirty flag. The poll does the redraw (and UI_REFRESH, if wanted).

### Cost of one knob write (estimate, needs a probe)
- fx_set_param body plus the 11 descriptor calls: about 300-600 cycles warm. Cold (DDR, L1P/L1D misses) about 1-3 k cycles.
- Effect edit callback: unknown, depends on the effect, estimated 100 to 5 k cycles. Filters or pitch effects that recompute coefficients are the worst case.
- Budget rule: at most 1-2 effect knob writes per block, round-robin, so the worst case stays under about 10 % of a block.

### Lag ramp
- Mixer targets: ramp every block. It is free (byte store), and engine smoothing already removes clicks.
- Effect knobs: params are integers (typically 0-100 or 0-150), so a ramp only writes when the integer value changes. A 1 s Lag over 100 steps is about 1 write every 55 blocks, which is cheap.
  - Fast Lags on many knobs at once share the budget of 1-2 writes per block, round-robin.
  - The error is a few blocks (well under 1 ms per write).

### If instead everything is deferred to the 16 ms poll
- Timing error: 0-16 ms, about 8 ms on average, plus task jitter. Block-exact is 181 µs (8 frames at 44.1 kHz).
- At 120 BPM a beat is 500 ms, so 16 ms is about 1/31 of a beat. That is an audible flam on hard cuts and on/off at a bar line.
- Acceptable for slow Lag ramps; not acceptable for quantized cuts, which the brief wants on the grid line.

### Confidence
- Mixer path: high.
- fx_set_param body with no UI and no pend: high (disassembly).
- The semaphore is the lock and all callers hold it: high.
- The effect callbacks are safe to run with interrupts off in the audio context: LOW. They normally run from the UI/MIDI task, and some may touch DSP-side state that the chain is using right now. Writes are atomic with respect to the chain because we run between slots, but this is unproven.
- Cycle numbers: low (estimates).

### Open points / probe
1. Time one fx_set_param from engine_run for each effect type in a test patch: knob 2-9 and on/off. Use TSCL before and after, and keep the max.
2. Check that the audio does not glitch when on/off is toggled from audio (on/off may hit the DSP-off mask and callbacks).
3. Confirm how the B14[191] count can be read safely (layout of the SYS/BIOS Semaphore object: count word offset).
4. Fallback if a callback misbehaves from audio: queue the write to the poll for that effect type only (16 ms error), and keep mixer moves block-exact.

### Verdict
- Mixer: GO.
- Effect knobs / on/off: NEEDS-PROBE. Design: try-lock from audio, with the poll as fallback.

---

### Q6. LED countdown from the firmware side

### How the stock LED task works (high confidence, disassembly)
- The task loop at 0xC00C744C runs Task_sleep 0xC00CEBC0(16), then calls 0xC00C7360. That function handles the blink modes:
  - blink-mode word 0xC0097C38 == 1 toggles every 500 ms (time kept at 0xC0097C50);
  - otherwise it calls 0xC00C7240;
  - tempo overlays 2 or 5 (0xC00CCD6C) call 0xC00C7264, which uses B14[109-111].
- Then, at 0xC00C73F4, it compares bit 0 of the desired word 0xC00EEB08 with bit 0 of the applied word 0xC00EEB10.
- Only when they differ does it call the GPIO writer 0xC00CD3B4(0, 1-desired) and set applied = desired. That update is an LDW / CLR / OR / STW sequence, not atomic.
- These code paths write the desired bit:
  - 0xC00BA860 (on/off of the effect under the cursor, plus the DSP-off mask; runs on patch or cursor changes);
  - 0xC00C7240;
  - 0xC00C72C4-72E6;
  - 0xC00C7320 (B14[108] flag, set by 0xC00C75D4 after a footswitch toggle);
  - 0xC00C74E0;
  - init: 0xC00C7538 / 0xC00C75B0.

So the stock task writes GPIO only on a change between desired and applied. That is the lever.

### Plan
Reuse the looper's GPIO path. The pointer at 0x1181DEF0 is the GPIO bank; looper.S publishes it as LEDON / LEDOFF / LEDMASK in the services block at 0xC00F3000.
- CLR_DATA (+28) with mask 1 lights the LED (pin 0, active low).
- SET_DATA (+24) darkens it.

While Perform owns the LED, every block, from engine_run:
1. Copy bit 0 of desired (0xC00EEB08) into applied (0xC00EEB10). The stock task then never sees a difference and never writes GPIO.
   Every block is needed because the stock writers may change desired at any time; with interrupts off our copy is atomic. The task's non-atomic read-modify-write can at worst lose one copy, and the next block (181 µs later) fixes it before the task's next 16 ms pass.
2. Compute the countdown level with the looper's formula:
   ```
   k=4; while(k<64 && 2k <= (pu-gu)>>2) k*=2;
   lev = ((gu&(k-1))+gf < k/2) ? on : off
   ```
   Add the PWM brightness counter (pwm = (pwm+1)&31; lit = pwm < lev) if dimming is wanted.
3. Write the GPIO register every block (CLR_DATA when lit, SET_DATA when dark).
   Do not write only on change. The looper's write-on-change has a weakness: a stock write in between sticks until the next edge. A write every block costs about 5 cycles and closes that hole. The same fix applies to looper.c.

On release (countdown done or move cancelled):
- XOR bit 0 of applied 0xC00EEB10, as looper.S already does when it leaves the looper.
- The stock task then sees a difference on its next pass (within 16 ms) and restores the normal LED.

### Arbitration with the looper ZDL
- Perform owns the LED only while it has a countdown pending.
- Otherwise the looper's S_MINE rule applies: the cursor is on the looper slot and MODE (B14+320) == 0.
- Simplest rule: add a word "PERF_LED" in the services block at 0xC00F3000. The looper skips its LED writes while it is set.

### CPU / RAM
- About 20-50 cycles per block while active, 0 otherwise.
- About 16 B of state.

### Confidence
- Stock task compares desired with applied and writes only on a difference: high.
- GPIO pointer and active-low pin 0: high (looper.S works on hardware).
- No other code writes this GPIO pin directly (bypassing 0xC00CD3B4): medium. I only checked the callers of the writer.

### Open points
- With the tempo overlay or the 500 ms blink mode active, desired toggles. We copy it, so it is harmless, but the user loses those blinks during a countdown. That is intended.
- Countdown display at a fast tempo: the period k gives a minimum blink of 4 units, which is half a beat. That is fine at normal tempos.
- If the mixer hook is absent, the same "no per-block hook" point from Q2 applies.

### Verdict: GO

---

### Addresses used (OS 2.10)

| What | Address | Confidence |
|---|---|---|
| Audio call list / stock slot loop | 0x1181BDE0 / 0x1181BE00 | high |
| Pre-chain step, interrupts off | 0x1181AFA0 | high |
| Transport block (L2) | 0x1181FF00 | high (repo) |
| Looper services block | 0xC00F3000 | high (repo) |
| Mixer base / LIVE[] | 0xC00F6000 / +224 | high (repo) |
| Free code RAM | 0xC00FCC40-0xC0102000 | high (docs) |
| fx_set_param | 0xC00BB600 | high |
| Param descriptor | 0xC00B056C (+12 max, word 11 bit 2, [7] callback) | high |
| Patch copies | 0xC009BF58 / 0xC009C1A0 (+44*slot + 4*param) | high |
| DSP-off mask | 0xC009C060 | high |
| Effect-edit semaphore | B14[191] (B14 = 0xC00EF748) | high |
| Semaphore_pend / post | 0xC00C7EE0 / 0xC00D6B00 | high |
| UI_REFRESH / Event_post | 0xC00ACD84 / 0xC00CBF40 (B14[656], 0x40) | high |
| LED desired / applied | 0xC00EEB08 / 0xC00EEB10 (bit 0) | high |
| LED task loop / GPIO writer | 0xC00C744C / 0xC00CD3B4 | high |
| GPIO bank pointer | 0x1181DEF0 (+24 SET, +28 CLR, mask 1) | high |

## P0 answers: 4 (clock), 5 (looper), 7 (storage)

Static read of docs, yamls, asm, looper.c. No disassembly was needed.
Paths are relative to C:\Users\lucam\OneDrive\Documenti\GitHub\zoom-ms-modding unless noted.

### 4. Clock on the 70CDR: GO (confidence high)

Answer
- The block is already the 70CDR build. patches/midi-clock.yaml says "MS-70CDR 2.10 OS", builds
  [ms70cdr-2.10], hooks 0xC00AEEE0 (Task_MIDI byte loop) and 0xC00C6998 (16 ms poll). The release set
  (scripts/midistomp_builder.py:23) already includes midi-clock. Every hook address is "high" in
  docs/dev/ms70cdr-addresses.md:89-104. The block stays at L2 0x1181FF00 (ms70cdr-addresses.md:21, 362;
  fixed because effects read it).
- All fields are valid on the 70CDR (docs/dev/transport-block.md:15-22): magic 0x5A4D5401, sequence,
  running, start counter, clocks since Start, tempo x100. Nothing in the port marks one as missing.
  (transport-block.md line 5 still says "MS-50G 3.10 OS only": stale text, the yaml is 70CDR.)
- Tempo with no MIDI clock: YES, it is in the block. The poll (asm/midi_clock/poll.S:11-14, 71-86)
  copies the patch TEMPO (tap, TEMPO setting, patch load) into word 5 as BPM x 100 within 16 ms of a
  change, whenever the clock is not live. 120.00 at power-on until the first copy. The pedal's own
  tap and tempo-hold (HOLD FOR = TEMPO) write the patch TEMPO, so they show up the same way
  (transport-block.md:34-39).
- While a clock is live: tempo = measured clock tempo (0.1 BPM steps, each beat). A hand TEMPO change
  is overridden on the next beat. After the clock stops (Stop or 0.5 s) the last clock tempo stays
  until TEMPO changes.
- Start (0xFA): running = 1, start counter +1, clocks = 0; the first clock after it (value 1) is the
  downbeat. Stop (0xFC): running = 0. Continue (0xFB) and Song Position are ignored. No clock for
  0.5 s (also 0.5 s after a Start with no clock) clears running (poll.S:60-68).
- Patch change: does NOT touch running, start counter or clocks. It changes the patch TEMPO. With no
  clock live, the poll copies the new patch tempo into word 5 (the grid tempo can jump at a patch
  load). With the clock live, the clock tempo wins again on the next beat. TEMPO LOCK (midi-settings,
  called at poll.S "out:") can put the kept tempo back after a patch change.
- MIDI SETTINGS TRANSPORT RECEIVE = OFF ignores Start/Stop/clock count and clears running.
  Perform must treat running = 0 as "free-running on the tempo word", as the looper already does.
- Clock without Start: the tempo follows, but running stays 0 and clocks do not count, so there is
  no bar position from the block. Perform needs its own sample/beat counter then (the looper does
  this in looper.c).

Sources: docs/dev/transport-block.md:15-39, 62-75; asm/midi_clock/poll.S:1-14, 60-120;
patches/midi-clock.yaml:1-40; docs/dev/ms70cdr-addresses.md:89-104, 354-362.
Open: (a) no doc records an on-pedal read of the block on a 70CDR, but v1.2 ships it; (b) decide
whether a tempo jump at a patch load (no clock, TEMPO LOCK off) is acceptable for quantized actions.
Verdict: GO, no probe needed.

### 5. Looper as a When source

### 5a. Are length, position and cycle counter published? NO today. GO if 3-4 words are added.

- Services block words (docs/dev/looper-services.md:19-36, asm/looper/services.inc:4-24): press counter
  (11), under-cursor flag (12), LED regs, claim and heartbeat (8, 9), 8 status chars (17-18),
  progress 0..256 (19), inverted flag (20). No length, no cycle counter, no event counters, no state
  word.
- Progress 0..256 is the only numeric position. It is a fraction of the loop, so the length in bars
  is unknown. A cycle count could be derived from wraps (progress dropping) with the 16 ms poll, but
  that is a guess, not a published value.
- State is only the text chars (EMPTY, REC, PLAY, STOP ...): readable, but not a stable API.
- The ZDL already keeps ev_rec, ev_stop, ev_del counters (zdl pack looper.c:86, 207, 552, 563-566),
  but in its own arena, not in the block ("kept for Perform mode's events").
- Free words in the block: 21, 22, 23 (offsets 84, 88, 92) and 30 (offset 120). Words 24-29 are
  firmware private, 31 is the end mark. Proposed, written by the ZDL once per block next to progress:
    21  LS_STATE  0 empty, 1 rec, 2 play, 3 stop, bit 8 = an action is pending
    22  LS_LEN    loop length in 1/16 notes (looper.c has it as U; state the unit in the doc)
    23  LS_CYCLE  +1 on every loop wrap while playing, cleared on record / delete
    30  LS_EVENTS ev_rec | ev_stop << 8 | ev_del << 16 (8-bit wrapping counters, like the press counter)
  Position in 1/16 notes = progress x LEN / 256, or add it as a word if more room is wanted.
  The doc rule is "never change the layout without a new magic": adding fields in free words that an
  old ZDL never writes (they read 0 = unknown) does not break it, but it should be written into
  looper-services.md; a version bump to 0x5A4C5302 is the clean way if firmware must tell.
- Perform should read them only while the claim is held (word 8 != 0 and the heartbeat moves). The
  claim is freed after 3 polls (~48 ms) without a heartbeat (looper-services.md:48).
Sources: docs/dev/looper-services.md:19-36, 48-56; asm/looper/services.inc; zdl pack
src/custom/looper/looper.c:86, 127-147, 207, 552-566, 767-800.
Confidence: high on "not published", medium on the exact words and units (design).

### 5b. Can patches/looper.yaml go into the 2.0 mixer build? GO, with one chain fix (confidence medium-high, static only)

Address check (section sizes computed from the yaml data):
- looper hooks 0xC00F2200-0xC00F2800 (1536 B, ends exactly where midi-cc's handler starts);
  services 0xC00F3000-0xC00F3080.
- mixer.S 0xC00F6000-0xC00F68C0 (2240 B). C section 0xC00F8000-0xC0100520 (34,080 B).
- No overlap with the looper. m0-probe (0xC00F3100-0xC00F53C0) is probe-only.
- NOTE: the C section ends at 0xC0100520, not 0xC00FCC40 as mixer-mode-m3-research.md:244 says. Free
  DDR below the looper buffer (0xC0102000) is about 6.8 KB, not 21 KB. Matters for Perform code and
  for storage (see 7).

Shared hooks (same patched address in both yamls):
- 0xC00C82D0 (poll trampoline): CONFLICT. looper.yaml and mixer-m2.yaml (line 116-119) both replace
  midi-clock's trampoline and both expect midi-clock's original bytes. Whichever applies second fails
  its `expect`, or one hook is lost.
  Fix: keep the mixer's trampoline (-> mixer poll, vector +120 at 0xC00F6078), and make the mixer's
  final jump (asm/mixer/mixer.S:102 `.equ POLL, 0x1181E800`, used near line 682) go to the looper's
  vector +0 (poll_pre, 0xC00F2200). looper.S:31-60 says poll_pre is "called instead of poll.S", calls
  POLL_HOOK itself and returns A4 = ticks, so the chain is mixer poll -> looper poll_pre -> poll.S.
  Drop the poll-trampoline write from looper.yaml in the combined build. Regenerate the hex and fix
  tests/test_looper_patch.py and test_mixer_patch.py.
- 0xC00D2F30 (footswitch toggle) and 0xC00D4270 (hold): tempo-hold and looper only. mixer-m2.yaml
  does not touch them. OK.
- 0xC00BB190 (CC trampoline): midi-cc and looper only. looper cc_pre chains to the midi-cc handler
  (0xC00F2800); the mixer hooks inside that handler (0xC00F2818 -> cc_link). Chain is
  looper -> midi-cc handler -> mixer cc_link: compatible.
- 0xC00BB0EC (draw call before the LCD send): looper only. The status box draws only while word 12 = 1
  and no overlay is open.
- The L2 entries the looper jumps to (0x1181E800 poll, 0x1181FA98 toggle, 0x1181FF20 hold) are the
  midi-clock / tempo-hold ones. mixer-m2 edits settings.S code at 0x1181EF78 / F0B0 / F0F0 only.
- Order: release set (midi-cc, midi-clock, tempo-hold ...), looper, m0-probe if kept, mixer-m2.
Not checked: a combined build was not run or flashed. Whether footswitch presses on the mixer's own
screens reach the looper hooks is not checked (they are play-mode hooks, so probably not).
Sources: patches/looper.yaml:16-55; patches/mixer-m2.yaml:90-120; asm/looper/looper.S:1-70;
asm/mixer/poll_trampoline.S; asm/mixer/mixer.S:70, 102.
Verdict 5: GO. Needs a combined test build (needs-probe for that only).

### 7. Storage for Perform assignments: GO for a compact table in record 50, NO-GO for 30 KB

How the store works (docs/dev/mixer-mode-m0.md:119-123, 225-266; mixer-mode-m3-research.md:97-110)
- Two banks, 140 KiB each (0x3B7000, 0x3DA000), log-structured: 24 B header + data appended per save.
  When full, compaction copies the live records 0-51 to the other bank and erases the old one.
- Records: 0-49 patches (122 B), 50 globals (was 24 B, now 824 B), 51 last patch (4 B). Size table at
  0xC00EA8E0. A save writes the whole record. The header marker is written last, so a power cut keeps
  the old record (atomic per record).
- Record 50 is wrapped by r50_load / r50_save (asm/mixer/pages.c:262-276): RAM image at 0xC00F7000,
  compaction buffer at 0xC00F7400 (both 824 B), size entry at 0xC00EA9A8, hooks callp 0xC00BA798 (load
  at boot) and 0xC00BA3F8 (save), buffer pointer mvk/mvkh at 0xC00B48C0 / C8. No new id, no format change.
- The live data is about 8 KB of about 130 KB free per bank.

Options
1. Bigger record 50.
   - 30 KB (600 B x 50): every R50 save writes 30 KB, so compaction every ~4 saves. Wear is still OK
     on paper (100k erases), but each compaction is a 140 KiB erase plus a copy (time not measured),
     and it needs 2 x 30 KB RAM buffers with only ~6.8 KB free DDR. NO-GO.
   - Compact table (8 controls x 8 B = 64 B/patch = 3.2 KB, R50 = about 4 KB): save = 4 KB + 24 B,
     so compaction about every 30 R50 saves. RAM: 2 x 4 KB. Fits only if the release build drops
     m0-probe (frees 0xC00F3100-0xC00F6000, about 12 KB), or use 32 B/patch (4 B/control): 1.6 KB
     table, 2 x 2.4 KB images, fits in the 6.8 KB gap.
   - Effort small: the hooks exist. Atomic with the mixer table. Risk: a bug damages record 50, not the
     patch records. Limits are the mixer's: editor / SysEx store gets defaults, a cut between patch
     save and R50 save loses the new assignment, a downgrade (stock size 24) drops the table.
   - Effect Manager / updater: they write the effects FS (0x0F0000-0x3B6FFF) and the OS; the banks
     0x3B7000-0x3FCFFF are not in that range, and MIDISTOMP builds only erase BIN/133. Same as the
     mixer table today.
2. New record 52: needs a size entry, id limits 51 -> 52 in REC_SAVE and REC_LOAD, compaction count
   52 -> 53, boot loop, and moving the 52-word index (5 code references to 0xC009D700)
   (mixer-mode-m0.md:310-320). Two separate commits (patch vs record). Changes the format that holds
   all patches. NO-GO: no gain over option 1.
3. File in the effects FS (17 free blocks = 68 KiB): room is fine, but Effect Manager and the updater
   rewrite that FS, whether they keep unknown files is unknown, and the OS FS write path was never
   studied (mixer-mode-m0.md:233-235). It also takes blocks users need for ZDLs. NO-GO unless probed.
4. Extra bytes in each 122 B patch record: atomic, but the 122 B size is built into many callers, and
   the spare bits are used or too few (byte 17 per slot is the mixer's; bytes 14/15 are not free, M3b7).
   NO-GO.
5. Smaller format (only used controls, 4-8 B each): not an alternative, it is what makes option 1 fit.

Recommendation: record 50, a Perform table after the mixer table, at most 64 B per patch (3.2 KB),
32 B if RAM is tight, keyed like the mixer table (hash of effect ids + name, same load order).
Before building, settle three numbers:
 (a) how often r50_save runs (on every patch save?). Save it only when the data changed;
 (b) where the two buffers go (m0-probe out of the release frees 12 KB; else 32 B per patch);
 (c) the compaction time of a 4 KB record (a short probe build).
Sources: docs/dev/mixer-mode-m0.md:119-123, 225-266, 296-335; mixer-mode-m3-research.md:97-110, 240-246;
asm/mixer/pages.c:262-276; docs/dev/mixer-mode-plan.md:120.
Confidence: high on the mechanism (the mixer ships it), medium on the RAM placement, low on the
compaction time (not measured).
Verdict 7: GO (compact record 50). 30 KB is a no-go and decides the data format.

### Summary
- 4: GO. All fields valid; tempo without clock is in the block; patch change leaves run state alone.
- 5: not published today; add words 21, 22, 23, 30 (state, length, cycle, events). looper.yaml fits the
  mixer address map; one real conflict at 0xC00C82D0, solved by chaining mixer poll -> looper poll_pre.
- 7: use record 50, 3.2 KB table. Free DDR is only about 6.8 KB (not 21 KB), so buffers need a plan.
- Not checked: combined build on the pedal, flash erase time, whether the release keeps m0-probe.

