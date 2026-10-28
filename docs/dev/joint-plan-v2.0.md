# v2.0 joint plan: firmware + effects pack

Coordinator run "midistomp-before-release", 2026-10-28. Specs: firmware "Before release" in
[repo-refresh-plan.md](repo-refresh-plan.md); effects `docs/STEREO.md` and `docs/NEW-EFFECTS.md` in
zoom-ms-zdl-effects-pack. This file wins where they differ.

## 1. What the effects need from the firmware

**Footswitch down (RISER hold).** Transport block word 6, `0x1181FF18` (reserved and 0 today, so
older firmware reads 0 and RISER falls back to press-only). No version bump: the magic stays `0x5A4D5401`.
- When (Luca, 2026-10-28): on the effect screen only when HOLD FOR is set to the momentary option; in
  PERFORM MODE (footswitch on an effect's on/off) always. Otherwise it stays 0 and the stock hold
  (TAP, tuner) runs as today.
- Value 1 while the pedal's footswitch is physically down, 0 when up. Written by the firmware's 16 ms
  footswitch poll (`asm/midi_clock/poll.S` round) from the switch state the OS reads, so it lags the
  switch by at most 16 ms. Set before the stock flip runs on the press (set it in the toggle path too,
  so the flip and the flag land together); cleared on release. MIDI CC never sets it.
- RISER rule: on any on/off flip, if word 6 = 1 the flip came from the footswitch. Still 1 after 0.5 s:
  hold (rise at Len speed, sit at the top), drop when it goes 0. Otherwise a timed sweep.

**Hold claim (so a RISER hold doesn't also fire TAP or the tuner).** Transport block word 7, `0x1181FF1C`.
- RISER writes its params pointer (`ctx[1]`, as the looper's S_CLAIM) every audio block while it is
  loaded. The firmware's 16 ms poll writes 0 every round, so a removed RISER frees it within one poll.
- PERFORM MODE only (the effect screen needs no claim: its momentary hold is no TAP/tuner). PERFORM's
  hold handling skips the stock hold action (HOLD FOR =
  TAP / tuner) when word 7 equals the params pointer of the slot under the cursor (slot state word 1,
  `SLOT_STATE + 212 x slot`). ponytail: a hold landing in the ~0.2 ms between a poll's clear and the
  next block fires the stock action once; fine for a 0.5 s gesture.

**Meter firmware check (LOUDER, Gooey).** Run the meter only when `*(u32*)0x1181FF00 == 0x5A4D5401`
and `*(u32*)0xC00F3000 == 0x5A4C5301` (looper services, MIDISTOMP v2.0 on the MS-70CDR). Anything
else: static cover. The meter stays switched off on the pedal for this build (NEW-EFFECTS.md).

**MIDI clock:** unchanged, `docs/dev/transport-block.md` words 0-5.

## 2. What the firmware needs from the effects

**Looper bar over other effects / sticking after leaving GRDLOOP.** Firmware bug, no effects change.
- `asm/looper/looper.S` `poll_pre`: when S_MINE goes 1 -> 0 it only re-arms the LED; it never posts
  EV_REDRAW, so the box pixels stay until the stock view redraws that area. Fix: post EV_REDRAW on
  that falling edge too.
- The claim lives up to STALE_POLLS (~48 ms) after GRDLOOP goes, and a new effect in the same slot can
  get the same params pointer, so the first draw of a new patch can still see S_MINE = 1. Fix: clear
  S_CLAIM (and S_SLOT = -1) on patch load; the ZDL re-claims within one block (`looper.c:664` claims
  when free and EMPTY). If the patch-load hook costs more than a few lines, check the slot's effect id
  instead. Test: host or pedal, GRDLOOP -> StompDly patch change, bar gone; cursor off GRDLOOP, bar gone.

**GRDELAY (GridDly) ~1 s dropout on footswitch with stereo input:** the effect. The firmware's flip path
is the same for every effect and stock effects don't drop out. Fixed in the effects stereo port
(reproduce in a host test first, per STEREO.md). Only if the host test can't reproduce it and the pedal
still does after the port does it come back to the firmware.

## 3. Order of work (one session per topic)

The scheduled run had no session-starting tool, so each topic runs as a background agent of the
coordinator with the same split and file ownership.

Firmware code sessions share `patches/*.yaml`, the TI build and `asm/perform/`, so they run one after
the other in the main checkout (no worktrees: nothing gets committed, so a worktree's work would be
stranded). Research and the effects repo run in parallel.

| When | Session | Repo / files it owns |
|---|---|---|
| now | 1. Beta1 bugfixes | firmware `asm/looper/`, `asm/perform/` (looper cycle, bar blink, knob->footswitch), `patches/`; effects `src/custom/looper/`, `tests/looper_*` |
| now | 2. Modwerk | `docs/dev/modwerk-research.md` + draft replies only |
| now | 3. Effects pack | effects repo except `src/custom/looper/`, `tests/looper_*` |
| now | 4. Release/docs | README, About text, `docs/user-guide.md`, `docs/dev/roadmap.md`, `docs/dev/v2.0-brief.md`, `pyproject.toml`, `docs/releases/` |
| after 1 | 5. Firmware release blockers | firmware code: footswitch-down flag + hold claim first (RISER codes against section 1 meanwhile), then release builder v2.0 (version-2.0.yaml, DSP 300 ships), PERFORM defaults, MENU, SETTINGS, VERSION/MODS, boot, effect select, research items |

Only session 4 edits user docs; sessions 1 and 5 report guide changes to the coordinator, who passes
them on. Only the coordinator edits this file and `repo-refresh-plan.md`. RISER is 4th in the effects
order, so the flag interface above is enough; session 5 confirms the addresses on the pedal build.

Decisions taken here: **Overdub** is not a feature (Luca, 2026-10-28): it comes off the test list
and isn't planned. The PERFORM-defaults guide/brief lines (`user-guide.md:395`,
`v2.0-brief.md:698`) are edited by session 4 once session 5 lands the code.

**Session 1 done (2026-10-28, not on a pedal, not committed).** Looper bar redraw + clear claim on
patch change; PERFORM bar blinks on the GRDLOOP's pending action; knob on Footsw follows/sets on-off;
PERFORM CYCLE drives the looper only while the LOOPER row is ON; PERFORM counter runs without MIDI
clock from the first FOOTSW press; truncated mono shows " M". 32-bar cycle is not a bug (halves to fit).
- **Space:** the mixer/perform C section (`patches/mixer-m2.yaml`) has 32 bytes left; looper hooks 4.
  Session 5 must free space before adding to `asm/perform/` or `asm/mixer/`.
- `tests/test_looper_patch.py` skips here (no GNU tic6x binutils); hex came from the TI assembler,
  which reproduced the old hex byte for byte. Luca accepted the TI check for beta2 (2026-10-28); GNU
  binutils exist on no machine here (they need Linux/WSL).
- Guide changes for session 4: memory table (`user-guide.md` ~472: 8 bars stereo from ~79 BPM, 4 bars
  from ~40), " M" for truncated mono, PERFORM CYCLE needs LOOPER ON, counter starts at first FOOTSW
  press without clock, knob on Footsw (click toggles, turn sets), 32-bar cycle records 16 mono at 120
  (counter shows the cycle), `looper-services.md` word 21 note is outdated.

## 4. For Luca
- **On hold (Luca, 2026-10-28). Editor-mode exit loses a change made 2-5 s before (Marti):** needs a stock 2.10 pedal to confirm
  it's stock behaviour. If it is, the guide gets a note.
- **Modwerk** (`docs/dev/modwerk-research.md`, drafts at its end, nothing sent): pick the hello (A: version
  tag in the identity reply, data only; B: own SysEx on id 7D, needs the unmapped 70CDR send routine);
  publish the byte 17 / record 50 table for their editor; capture a
  stock flash on your pedal for them.
