# Repo refresh for v2.0: plan

Decided with Luca, 2026-10-23. Example to borrow from: themanro/ZoomMultistompZDL.

## 1. Images
- **Banner:** Luca makes a new one himself: a face-on MS-70CDR close-up with the v2.0 boot screen and no ZOOM
  logo. Done: docs/img/banner.jpg.
- **Cover:** done: docs/img/cover.jpg (MS-70CDR with KALEIDO on the screen).
- **Five screens, all rendered from the real draw code, in one style (same scale, same frame):**
  - Mixer chain screen
  - PERFORM MODE
  - one MASTER page
  - MIDI menu (re-render of the v1 shot)
  - MIDI clock tempo popup (re-render of the v1 shot)
  - First check: is there a render path for the stock-UI screens (MIDI menu, tempo)? If not, draw them from the
    old shots in the new style.
- The boot, HOLD FOR and TURN OR TAP shots leave the README. The guide keeps them only where they help.
- Social preview image for the GitHub page (1280x640), cut from the cover.

## 2. README, rewritten
Order:
1. Banner
2. MIDISTOMP 2.0 and a one-line pitch
3. Links: Guide, Download, MIDI chart, Demo, Effects
4. Support badges (GitHub Sponsors, Buy Me a Coffee, PayPal) and one line: "MIDISTOMP is free and made by one
   person. If it's useful to you, a coffee keeps it going."
5. New here? A short plain intro: what it is, what you need, and that patches and effects are kept.
6. Cover photo
7. What 2.0 adds, with the mixer, perform and master screens:
   - MIXER (parallel/split routing, chain screen, PEDAL INPUT, limiter)
   - PERFORM
   - LOOPER (GRDLOOP)
   - MASTER (with KALEIDO)
   - stereo effects
8. MIDI: the 1.x features table, with the MIDI menu and clock screens. It gets the same weight as section 7.
9. Custom effects pack
10. Install in three steps, with a link to the guide
11. Compatibility: tested, confirmed by users, not supported (the Plus and Four series)
12. FAQ and troubleshooting: bricking, going back to stock, Mac, which effects work, where to report
13. Demo video
14. Feedback and Support
15. For developers: short. Links to docs/dev/, Contributing, Related projects, License.

## 3. User guide, rewritten as one file
1. Overview
2. Install and recovery (Mac included)
3. One chapter each for MIXER, PERFORM, LOOPER and MASTER: what it does, the knobs (3 press = next page, 1 press =
   page option, 2 = EXIT) and one screen
4. MIDI and the CC chart
5. Settings
6. Effects and Effect Manager
7. Known limits and FAQ
8. Feedback

## 4. Docs move
- `docs/` keeps the user files: user-guide, flashing, safety, releases and img.
- Plans, research, mockups and HANDOFF move to `docs/dev/` (with `git mv`), with an index `docs/dev/README.md`.
- Fix every link to the moved files: README, the docs, the scripts and the tests.

## 5. Other
- `docs/releases/v2.0.md`: release notes, also used as the GitHub release text.
- GitHub page: a description and topics written down for Luca to set; the social preview image.
- `.github/ISSUE_TEMPLATE/`: a bug report form (pedal, MIDISTOMP version, steps, what happened) and a feature request form.

## Open
- The text for the stereo effects waits until they are done in the other session.
- Redo the custom effects cover (README > Custom effects, `release/covers.png` in zoom-ms-zdl-effects-pack) in the
  v2.0 look.
- Redo the demo video (README > Demo): the current one is v1 on an MS-60B. Show v2.0 on the MS-70CDR.

## Future
- Effect IDs and the category screen: open topic for after v2.0, see [future-effect-ids-and-categories.md](future-effect-ids-and-categories.md).

## Before release (firmware and guide)
All of these are done before v2.0 ships.
- **PERFORM MODE: no looper defaults.** A new patch with the looper starts empty: no footswitch -> looper Ftsw,
  no REC END -> MIX XFade B100, no DELETE -> XFade A100. Code: `asm/perform/perform_store.c:48-59` (and
  `perf_defaults` in `perform_engine.c:476`). Then drop the sentence from `docs/user-guide.md:395` and the default
  in `docs/dev/v2.0-brief.md:698`.
- **Release builder for v2.0:** `scripts/midistomp_builder.py` still builds v1.2 (`PATCHES`, `OUT_NAME`).
  Add `patches/version-2.0.yaml` (stamp V2.0) and the v2.0 patches. **DSP 300 ships in v2.0** (Luca,
  2026-10-28): split the `0xC00BB52C` write out of `diag.yaml` into its own patch (diag ships in v2.0 since session 5).
- **Mac updater:** improve it, clean it up, make it much easier to use.
- **SETTINGS:** the right softkey shows no arrows, so you can't tell that turning it changes the value. Add them.
- **SYSTEM > VERSION:** show the right content.
- **SYSTEM > MODS:** show the right content.
- **Boot screen:** implement the new v2.0 boot screen.
- **MENU order:** MASTER goes right after PERFORM MODE.
- **Footswitch on an effect's on/off (PERFORM MODE):** press and hold do exactly what they do on the stock effect
  screen. With HOLD FOR set to TAP, holding the footswitch works as it does normally.
- **Hold timing:** PERFORM's hold takes too long to register. Match the stock effect screen's hold time.
- **Looper bar on other effects:** the looper status bar (EMPTY ... NO CLK) sometimes shows over effects that
  aren't GRDLOOP (seen over StompDly). Fix the firmware's GRDLOOP detection. `asm/looper/looper.S` `poll_pre`
  matches the slot only by params pointer (S_CLAIM) and frees it after STALE_POLLS with no heartbeat. Suspects: a
  stale claim matching a new effect in the same slot after a patch change; no redraw when S_MINE drops to 0; or
  S_HB still beating. Likely fix: also check the slot's effect is GRDLOOP, or clear S_CLAIM on patch load.
  It also sticks on the screen after leaving GRDLOOP.
- **Looper bar blink in PERFORM MODE:** sometimes the bar doesn't blink in PERFORM MODE when it should.
- **PERFORM: knob targeting the footswitch:** a knob with the footswitch as its target shows as a toggle (fine),
  but gives no feedback on screen and doesn't work properly.
- **Effect select screen (QOL):** the screen you get by holding a cursor key on the effect screen shows 4
  categories on the MS-70CDR. Make it like the MS-50G's, which has 5 and includes drives and amps. Not researched
  yet.
- **Beta1 tester report (Marti, MS-50G via the Mac app, from M3B7):** flash, 50 patches, byte 17 conversion,
  GRDLOOP install, step 5 and step 9 all fine. Fix or answer:
  - **Looper cycle source:** with the looper on SYNC OWN and the PERFORM looper off, it still takes PERFORM's
    cycle length. It must use its own cycle.
  - **Looper without MIDI clock:** use tap tempo exactly like MIDI clock, and the footswitch press as the
    transport (start). Marti's 32-bar cycle at ~120 BPM stopped recording at 16 bars and played 16 while the
    screen said x/32; then showed "32.4/32". Luca can't reproduce; likely MIDI clock related. Check the
    32-bar stereo->mono switch (guide says mono records 16 bars at 120: is that right?) and the bar counter text
    (overlapping "REC 14/16 MONO 3.3/32", ".4" past the cycle).
  - **Overdub:** not a feature (Luca, 2026-10-28). Take it off the test list; don't build it.
  - **On hold (Luca, 2026-10-28). Editor mode exit (SysEx 51) within 2-5 s of a change loses it** (pedal reloads the stored patch before
    AUTO SAVE). Probably stock; confirm on stock 2.10, note in the guide if so.
  - Not tested yet: MIDI Start restarting a loop from bar 1.
- **Docs drift (outside review):** GitHub About oversells v1.2 (says routing/PERFORM/looper/meters shipped:
  fix with v2.0 release); `docs/dev/roadmap.md` stale (MS-50G base, MS-60B only); `pyproject.toml` 0.1.0 vs
  releases (single-source the version); two download targets (zoom-ms-modding vs zoom-ms-midistomp releases);
  v2.0 brief has internal `/mnt/project-files/...` paths.
- **Modwerk answers: done** (2026-10-28), `docs/dev/modwerk-research.md` sections 1-4, drafts at its end (reply
  sent by Luca 2026-10-29; promised items wait until after v2.0). Luca's decisions: hello A (identity tag)
  after v2.0, B later; DSP 300 in v2.0; publish the byte
  17 / record 50 table; capture a stock flash. **v2.0 with the stereo effects ships first, bug free; Modwerk
  comes after** (Luca, 2026-10-29). Follow-ups (after v2.0 unless marked):
  - MIDISTOMP identity tag: **done, tested** (2026-11-06), `patches/identity-tag.yaml` ("2.10" -> "M201";
    Effect Manager OK), branch `claude/modwerk-c47ff1`. Not in the release builder yet.
  - Flash capture: **done** (2026-11-06), `docs/dev/flash-protocol.md` (01/0A/02/04, CRC-32 per 2048-byte chunk).
  - **v2.0:** `midistomp_builder.py` also lacks looper and mixer-m2 in `PATCHES` (with the release-builder item above).
  - `docs/dev/patch-routing-bytes.md` (the byte table), after the pages.c / mixer.S comment fixes.
  - Stock flash capture on Luca's pedal, firmware data stripped from the log.
  - Effects pack: replace the Zoom blobs `linesel_handlers.bin` and `divf_rts.bin` (in every ZDL) and the stock
    attribute bytes.
  - Optional: YAML `expect` fields to sha256 (they hold ~900 B of stock OS bytes).
  - **v2.0:** `transport-block.md` and effects `src/custom/common/zmt.h:4-5` drift: they say MS-50G only, the
    0xC00CA630 poll site (70CDR: 0xC00C6998), words 6/7 reserved (release-blockers session, with words 6/7).
- **Research: PERFORM, one effect per control with a parameter per gesture.** A knob (or key) targets one
  effect, and each gesture drives a different parameter of it. Example: knob 1 -> a reverb, turn = decay/size,
  hold = freeze, knob press = the effect's footswitch on/off. Check the per-patch store layout (room per
  gesture), the PERFORM screen and setup UI, and how it fits the existing turn/tap/hold handling. Research
  only for now; report what it would take.
- **Research: Modwerk (browser build + flash, shared SDK): done** (2026-10-28), `docs/dev/modwerk-research.md` section 5.
- **Research: more than 6 effects.** Can a patch hold more than 6 effects, limited only by the DSP (300)
  instead of a fixed 6 slots? Check the patch format (slots per record), the chain/engine arrays, the effect
  screen and Effect Manager/editor compatibility. Research only for now.
- **GRDELAY (effects pack):** with a stereo signal, pressing the footswitch cuts the audio for about a second
  (fine in mono). Sent to the stereo effects session to fix.

## Order of work
1. Docs move and link fixes (mechanical).
2. Screen renders.
3. README.
4. User guide.
5. Release notes, issue templates, GitHub page text.
6. The cover, once Luca's photo arrives.

## Session 5 status (2026-10-29, not on a pedal, not committed)
Done: footswitch-down flag (word 6) and hold claim clear (word 7, `looper.S` poll); release builder v2.0
(`version-2.0.yaml`, `dsp-limit.yaml`, `midistomp_builder.py` BASE + looper, mixer-m2, dsp-limit); PERFORM: no
looper defaults, the footswitch acts on the press; comment nits (`pages.c` byte 17, `mixer.S` header).
Left for the next firmware session (C space and LOW: see "Done since (2)"):
- **Done since:** MENU order (MASTER is entry 3: `mixer.S` MENUSCR / MENU7, `chain_vec.asm` `ms_or` = entry 3 or 6,
  `master.c`, SETTINGS EXIT row 4 and version EXIT row 5 in `mixer-m2.yaml`, diag's name at MENU7[5] `0xC00F60D8`).
  PERFORM footswitch hold on a Footsw target (`perform_keys.c` `ftsw_hold`): nothing while the effect claims the
  hold (word 7 == the slot's params pointer); otherwise it works as HOLD FOR MOMENTARY whatever HOLD FOR is
  (Luca): the press flips, a release after 500 ms (`FTSW_HOLD_MS`, tempo-hold's `HOLD_MS`) flips back. A hold
  never opens TAP or the tuner (event 224 maps to no PERFORM control). C space now: 96 B free at `0xC0106D60`.
- **Done since (2):** C space: `pages`, `pedal_in` and `perform_engine` `.const` moved to LOW (`.lconst` in
  `scripts/build_mixer_ui.py`); C now ends at `0xC01068C0` (1280 B free), LOW at `0xC00F6EE0` (288 B to `0xC00F7000`).
  SETTINGS and MIDI lists: the stock turn arrows over knob 3 (`pedal_in.c`, `DRAW_ARROWS(2)`), not on the MIDI row.
- **VERSION / MODS page:** done (session 5, Luca's option a): `diag` ships in the release as SYSTEM
  (`midistomp_builder.py` PATCHES). Timing runs only while SYSTEM or the MENU list is open (diag_poll
  sets the magic word). MODS adds MASTER and KALEIDO: each measures itself while its screen is open
  (master.c master_poll, published at 0xC010A024/28) and MODS shows the last value, "-" before. Needs pedal tests.
- **Research (effect select, more than 6 effects, Mac updater):** first pass below, not on a pedal.
- **Boot screen:** the `fw_shot.py` `boot` render (boot-logo + version-2.0) already matches
  `docs/img/banner.jpg` (MIDISTOMP / MOD / v2.0). No change.

- **End steps (2026-10-29):** ponytail review of the uncommitted firmware: no must-fix (the fx-category table at
  `0xC00F2A00`-`0xC00F2AC0` overlaps no patch, the RAM test starts at `0xC00F3100`, looper buffers at `0xC0102000`+).
  `user-guide.md` and `flashing.md`: V2.0 updater name and patch list, SYSTEM MODS, SETTINGS/MIDI arrows, MASTER's
  menu place, PERFORM footswitch hold, DRV/AMP. Windows beta2 (label BETA2) built into
  `CLAUDE\MIDISTOMP v2.0 beta2 for testers` with the effect ZDLs and `v2.0-beta2-test-steps.md`; GRDLOOP not rebuilt.
  **Left:** every pedal test in that file; `docs/img/menu.png`/`menu-2.png` show the old MENU order (re-render via
  `scripts/screens`); Mac zip at release; the For-Luca items in `joint-plan-v2.0.md`.

### Research notes (session 5, from the release image in the emulator; addresses MS-70CDR 2.10)
- **Effect select, 5 categories.** SELECT CATEGORY (screen 33, "ADD EFFECT UNIT") draws its labels at
  `0xC00A9078`-`0xC00A90C0`: CHO (x 3), DLY (45), REV (87) on the top row, DYN/FLTR (24) below, strings at
  `0xC00E91E3`-`0xC00E91EF`, via `0xC00A8B34(text, x, y, len)`. The cursor box tables already hold **5**
  places (shared code with the MS-50G): x `0xC00ECA68` = 1, 43, 85, 22, 64; y `0xC00ECA80` = 10, 10, 10, 36,
  36. The cursor `B14[89]` is clamped to 3 in the key handler (`MVK 3` at `0xC00A7268`, `0xC00A7328`,
  `0xC00A7350`; `CMPGT 4` at `0xC00A7250`, `0xC00A7340`). So a 5th category needs: those clamps to 4, a 5th
  label at about x 66, y 38, and (not found yet) the table that maps a category to the effect list
  (`0xC00ECAC8[row]` holds the ids). Next: find who fills `0xC00ECAC8` and which ZDL category (gid) each of
  the 4 takes, then check the MS-50G 3.10 image for its 5 labels and its mapping. Pack effects are gid 8.
- **More than 6 effects.** Six is fixed in several places: the live patch is 6 x 44-byte records at
  `0xC009BF58`, the DSP-off mask `0xC009C060`, FX_TABLE `0xC00EE930[slot]`, the cursor table `0xC00EE748`
  (6 x view), and add checks `count < 6` (`0xC00C2018`); see `mixer-mode-m3-research.md`. The stored patch
  format (and so Effect Manager and the editors) also holds 6 slots. Verdict: not a patch, a rewrite of the
  patch format; any extra slot would not survive Effect Manager or a SysEx round trip. Park it.
- **Mac updater, easier to use.** Today the user unzips, then runs `xattr -cr` and `codesign --sign -` in
  Terminal (`docs/flashing.md`). Options, cheapest first: (1) put an `Install MIDISTOMP.command` next to the
  app in the zip that runs those two lines and opens the app (the user still has to allow it once in System
  Settings > Privacy & Security, since the .command is quarantined too); (2) ad-hoc sign at build time on
  Windows (e.g. `rcodesign`), so only the quarantine step is left; (3) a Developer ID signature and
  notarization: no warnings at all, but needs a paid Apple developer account. Recommend (1) now, (3) if Luca
  wants it fully clean. Also: the docs still say "V1.2 Updater".
- **Docs:** `docs/flashing.md` and the guide still name "MIDISTOMP V1.2 Updater"; the builder now writes V2.0.
- **Effects `src/custom/common/zmt.h:4-5`:** say MS-70CDR 2.10, poll site 0xC00C6998, words 6/7 = footswitch down / hold claim (sent to STEREO EFFECTS).
