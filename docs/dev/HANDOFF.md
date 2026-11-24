# Handoff: where the work stands (2026-11-24, after v2.0.4.1)

For a new Claude session running **locally on Luca's Windows PC**. Read this, then each repo's
CLAUDE.md. The October handoff it replaces (v2.0 probe rounds) is in git history.

## Repos

| Repo | What |
|---|---|
| [zoom-ms-midistomp](https://github.com/matujuice/zoom-ms-midistomp) | firmware mod (patches, asm, builder) |
| [zoom-ms-zdl-effects-pack](https://github.com/matujuice/zoom-ms-zdl-effects-pack) | the custom effects (.ZDL) |

Local paths: the effects pack clone is in `Documenti\GitHub`. ZDLs also go to
`C:\Users\lucam\OneDrive\Desktop\ZOOM MS FX\ZoomMultistompZDL-main\ZoomMultistompZDL-main\dist`.
TI compiler `ti-cgt-c6000_8.5.0.LTS` is in Downloads.

- Firmware: needs Zoom's official MS-70CDR v2.10 updater (never committed; set
  `MIDISTOMP_70CDR_UPDATER` for the tests). Release: push a `vX.Y.Z` tag; the `builder` workflow
  builds the Windows and Mac builders (no Zoom code) and publishes them with
  `docs/releases/vX.Y.Z.md`. Each builder makes a stock and a "(360MHz OC)" updater.
- Effects pack: `py build_all.py`, then `py make_release.py`, then a GitHub release with
  `dist/*.ZDL` and the zip (no CI).

## Where things stand

- **v2.0.4.1 released** on both repos (Latest). Release notes: [docs/releases](../releases/).
- **On hold** (Luca): the patch editor (PR 64, branch `claude/sysex-editor`, merge only when the
  editor is done) and the DSP bench (PR 76, with the Washout knob-crackle fix). The pack's synth
  effects (issues 45, 46) are paused too.
- **Waiting on others**: Roman's hardware check of the SysEx slot routing (issue 72); the Modwerk
  board question on model byte 0x57.
- Open issues live on GitHub; nothing else is in flight.
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
