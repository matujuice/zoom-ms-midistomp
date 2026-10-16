# Handoff: v2.0 work, 2026-10-16 (updated after probe v2 round 1)

For a new Claude session running **locally on Luca's Windows PC**. Read this, then each repo's
CLAUDE.md. It replaces a cloud session that could not reach the PC.

## Repos and branch

Both on branch `claude/epic-thompson-rggzx8`; pull both first.

| Repo | Head at handoff | What |
|---|---|---|
| [zoom-ms-midistomp](https://github.com/matujuice/zoom-ms-midistomp) | `f3e6bd9` probe v2 round 1 results | firmware mod (patches, asm, builder) |
| [zoom-ms-zdl-effects-pack](https://github.com/matujuice/zoom-ms-zdl-effects-pack) | `e5c854c` DirtBox/Choral shrink | the custom effects (.ZDL) |

Local paths: the effects pack clone is in `Documenti\GitHub`. ZDLs go to
`C:\Users\lucam\OneDrive\Desktop\ZOOM MS FX\ZoomMultistompZDL-main\ZoomMultistompZDL-main\dist`
(old builds backed up in its `backup-before-cpu-opt`). TI compiler `ti-cgt-c6000_8.5.0.LTS` is in
Downloads. **Locally you can build both repos yourself**; the cloud session could not.

- ZDLs: `py build_all.py [effect]` in the effects pack.
- Firmware: needs Zoom's official MS-70CDR v2.10 updater (never committed; ask Luca where it is,
  set `MIDISTOMP_70CDR_UPDATER` for the tests). Build line in
  [mixer-mode-m0.md, "Probe build"](mixer-mode-m0.md#probe-build-how-to-read-it).
  Releases are built and published by the `builder` GitHub workflow (`workflow_dispatch` with
  `release = vX.Y`); Luca never uploads anything by hand.

## Where things stand

- **v1.2 released** (no Looper): https://github.com/matujuice/zoom-ms-midistomp/releases/tag/v1.2
- **Looper** (v2.0 step 1): status bar always visible, only the bar blinks, countdown blinks capped
  at 1/8, Roll repeats the first slice. Done, not released.
- **Mixer Mode** (v2.0 step 3): plan [mixer-mode-plan.md](mixer-mode-plan.md) (M0-M4), research
  [mixer-mode-m0.md](mixer-mode-m0.md). M0 done; Route A for per-patch storage (repack P8 to free
  bytes 14, 15, 17 of each slot block). Probe v1 results are in mixer-mode-m0.md.
- **Probe v2** built and sent (`build/out/MIDISTOMP M0 probe v2.exe`, sha256 `6cfe2f50…270e`):
  version page 0, measures only while its screen is open, honest load vs 54,422 cycles/block,
  P6 CTX/BUS (where stock delays write), cursor fix, **DSP limit 300** (test only).
  **Round 1 photos read** (P2 + P3 CYC on two patches): results in
  [mixer-mode-m0.md, "Probe v2 results, round 1"](mixer-mode-m0.md#probe-v2-results-round-1-2026-10-16).
  P2 names match P3 rows (photos had only been paired wrong). Patch B summed ~71,500 cycles
  (> 54,422: overrun, its numbers are inflated). Cursor lookup still fails sometimes
  ("CUR 5 SLOT -107"). The rest of the v2 checklist is still open.
- **Effects CPU rewrite** (all 11 effects, host A/B vs old code: identical or below -80 dB, except
  Choral fix 3 at -23 dB worst on fast vowel moves, judged inaudible). First TI build: no errors, no
  `.switch`/`push_rts`. WaveFold's main loop may not pipeline ("did not find schedule").
- **DirtBox/Choral shrink done** (`e5c854c`, built locally): DirtBox 25,274 B, Choral 28,866 B.
  CGT 8.5 has no per-loop `NOSWP` and `--opt_for_space` pulls in `pop_rts`, so: DirtBox's
  per-model loops and `ab_prepare` became single `-O1` functions (`AB_SMALL_FUNC`); Choral uses
  `SR_NOSWP` (an asm NOP) on cold loops and `-O1` copies of init/text helpers. Host tests pass
  (run in the cloud after the commit). Not yet loaded on the pedal.
- **Did the rewrite raise CPU?** Possibly. In patch A, EuGate 3,338 / Scrub 4,288 / DubSiren 5,683
  avg vs 2,284 / 2,765 / 3,807 in the old table (STEREO.md); S.GN_L is 10% lower. Settings and
  patch differ, so not proven. Suspect: software pipelining grows code, and six effects + OS
  share L1P, so cache misses may eat the gain (host A/B can't see that). **Decide with an A/B on
  the pedal**: each effect alone, same knobs, new ZDL vs `backup-before-cpu-opt`, P3 CYC each.
  If new loses: smaller code (`SR_NOSWP`-style / `-O1` on loops) or revert that effect.
- **Declared DSP costs** (`dsp_cost` in each manifest, written by `build/linker.py`) are the
  pre-rewrite measurements; lower them after the probe measures the new builds (P3 CYC, about
  100 cycles per cost unit). Choral is 150 for now (it measured ~240).

## Next, in order

1. Pedal A/B (above): EuGate, Scrub, DubSiren alone, new vs old ZDL, P3 CYC; patch B again, P1
   only. Also load the shrunk DirtBox and Choral and check they run.
2. From those numbers: keep, shrink or revert each effect; then update `dsp_cost` in the manifests
   and the effects pack's docs/STEREO.md table. Fix the P2 cursor lookup (-107) in the probe.
3. Builder: **probe in every build except releases** (the release workflow input decides; no
   option to forget). The probe must move above the Mixer engine's DDR region (`0xC00F3100`+)
   before M1 uses it. Every dev build stamps page 0 (`--stamp label=...`).
4. **M1**: bus engine with fixed test layouts (mixer-mode-plan.md).
5. Small fixes: Looper `asm/looper/services.inc` `CURSOR_SLOT` is wrong (`0xC00EE948`; the cursor
   table is `0xC00EE748 + 24 x cursor`); `zt_update` in the pack's `src/custom/common/zmt.h` has a
   20-iteration mod loop per block (CPU, all tempo effects); EuGate's unused `ch_prepare` warning
   (used by host tests, harmless).
6. Later: stereo ports per the pack's [docs/STEREO.md](https://github.com/matujuice/zoom-ms-zdl-effects-pack/blob/claude/epic-thompson-rggzx8/docs/STEREO.md)
   (port most effects, the rest get mono-sum input (L+R)/2); Looper cost measurement; the final
   DSP limit value; Choral zipper check on fast vowels (fallback: always recompute, ~+900 cycles).

## How to work (Luca's preferences)

- Short English replies (he sometimes writes Italian). Link docs directly with GitHub URLs.
- Pedal tests: give **every photo needed for a step at once**, as one checklist.
- Mixer settings must be saved per patch. Downgrades and Zoom editors don't matter.
- Owner decisions per effect: the pack's docs/DECISIONS.md (don't undo).
- Say plainly what was and wasn't tested (no listening test, CPU not measured, etc.).

## Agent workflow (keep it; it was efficient)

- **Fan out** independent work to background agents, one per group of files, each in its own git
  worktree (`isolation: worktree`), so they never touch the same file. Group small effects 2-3 per
  agent.
- **Cheap models**: Sonnet for well-specified edits, docs and address work; Haiku for lookups;
  Opus only for hard design or the trickiest rewrite (Choral, firmware hooks, asm).
- Each agent prompt is self-contained: files to read (CLAUDE.md, rules docs, header comments), the
  hard rules, what "done" means, and **a verification it must run and report**: for DSP, a
  throwaway host harness (in the scratchpad, not the repo) running OLD vs NEW code on the same
  inputs across every mode, reporting max/RMS difference in dB; then the full test suite.
- Agents commit in their worktree and do **not** push. The main session reviews the report,
  cherry-picks, runs the full tests, adds any cross-cutting fix, and pushes once.
- Locally, add a last step the cloud could not do: build with the TI compiler and check size
  (< 28 KB per ZDL), `.switch`, `push_rts`/`pop_rts`, and which loops pipelined (`-k` asm).
- Commit trailer used so far:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (no model name elsewhere).
