# Handoff: v2.0 work, 2026-10-16

For a new Claude session running **locally on Luca's Windows PC**. Read this, then each repo's
CLAUDE.md. It replaces a cloud session that could not reach the PC.

## Repos and branch

Both on branch `claude/epic-thompson-rggzx8`; pull both first.

| Repo | Head at handoff | What |
|---|---|---|
| [zoom-ms-midistomp](https://github.com/matujuice/zoom-ms-midistomp) | `a871363` probe v2 | firmware mod (patches, asm, builder) |
| [zoom-ms-zdl-effects-pack](https://github.com/matujuice/zoom-ms-zdl-effects-pack) | `7a0a010` Choral CPU | the custom effects (.ZDL) |

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
  **Waiting for Luca's photos** (list in mixer-mode-m0.md, "What to send back (v2)").
- **Effects CPU rewrite** (all 11 effects, host A/B vs old code: identical or below -80 dB, except
  Choral fix 3 at -23 dB worst on fast vowel moves, judged inaudible). First TI build: no errors, no
  `.switch`/`push_rts`. 10 ZDLs copied. **DirtBox 39.7 KB and Choral 30.9 KB are too big** (36 KB
  hung the pedal; target < 28 KB). A task "Shrink DirtBox and Choral under 28 KB" was queued:
  try `--opt_for_space=1` (check no `push_rts`), then `NOSWP` on DirtBox's per-model loops and
  Choral's coldest loops. WaveFold's main loop may not pipeline ("did not find schedule").
- **Declared DSP costs** (`dsp_cost` in each manifest, written by `build/linker.py`) are the
  pre-rewrite measurements; lower them after the probe measures the new builds (P3 CYC, about
  100 cycles per cost unit). Choral is 150 for now (it measured ~240).

## Next, in order

1. Shrink DirtBox and Choral (above), copy, push.
2. Read Luca's probe v2 photos; update mixer-mode-m0.md. Then a P3 CYC round on the new ZDLs and
   update the `dsp_cost` values and the effects pack's docs/STEREO.md table.
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
