# Repo refresh for v2.0: plan

Decided with Luca, 2026-10-23. Example to borrow from: themanro/ZoomMultistompZDL.

## 1. Images
- **Banner:** Luca makes a new one himself: a face-on MS-70CDR close-up with the v2.0 boot screen and no ZOOM
  logo. I only put it in place at docs/img/banner.png.
- **Cover:** Luca makes a new photo to replace the Digitakt one. I put a KALEIDO render on the pedal's screen.
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
- The effect type chart: TBD.
- The text for the stereo effects waits until they are done in the other session.
- Redo the custom effects cover (README > Custom effects, `release/covers.png` in zoom-ms-zdl-effects-pack) in the
  v2.0 look.
- Redo the demo video (README > Demo): the current one is v1 on an MS-60B. Show v2.0 on the MS-70CDR.

## Order of work
1. Docs move and link fixes (mechanical).
2. Screen renders.
3. README.
4. User guide.
5. Release notes, issue templates, GitHub page text.
6. The cover, once Luca's photo arrives.
