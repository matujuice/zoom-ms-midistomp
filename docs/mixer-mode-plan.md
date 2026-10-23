# Mixer Mode: build plan (draft for Luca)

v2.0 step 3, on the MS-70CDR 2.10 base. The design is in `docs/v2.0-brief.md`,
"Phase 2: Mixer Mode". This file covers only **what gets built first and in
which order**, so each step ends with something Luca can flash and hear.

```
OUTPUT ← Post ← [MIX] ← Bus A ← [ROUTE] ← Pre ← INPUT
                      ↖ Bus B ↙
```

## What we know and what we don't

- **Known:** each effect gets three buffers from the OS: `ctx[4]` the dry input,
  `ctx[5]` the signal from the effects before it, `ctx[6]` an output it adds
  into (effects pack `build/ABI.md`). The chain is already stereo on both OSes
  (`docs/ms70cdr-port.md`). So routing should be possible without touching any
  effect: give Bus B effects their own pair of buffers, then sum.
- **Not known yet:** where the 70CDR OS sets those buffers for each slot and
  runs the six effects; how it counts DSP load ("DSP Full"); where a patch has
  room to store the bus of each effect and the node settings.

## Steps

| # | What | Luca hears / sees | Model |
|---|---|---|---|
| M0 | **Research, no build:** find the chain runner, the per-slot buffers, the DSP budget and spare bytes in the patch format on the 70CDR OS. Ends with a go / no-go and the hook points | nothing (a report) | Opus, Sonnet for the address work |
| M1 | **Engine with fixed test layouts:** the firmware runs Pre → Bus A + Bus B → sum → Post from a layout picked by a test build (e.g. slots 1-2 Pre, 3 on A, 4 on B, 5-6 Post), 50/50 sum, the safety limiter on the output | parallel effects really in parallel; no clicks; what happens at DSP Full | Opus |
| M2 | **The nodes:** `[ROUTE]` and `[MIX]` with their knob pages on the MIXER menu screen (the Effect Chain screen opens them from M3; Send, Crossfade with the Smooth / DJ / Cut curves, levels, Mode, Output Mode), saved per patch, MIDI CCs. Tested with a **routing probe** ZDL (a sound source, a filter and a delay in one effect, with a BUS: PRE / A / B / POST knob, Luca 2026-10-15); stock effects keep their bus from M3 on | playing Send and Crossfade by knob and CC, patches remember them | Opus engine, Sonnet UI |
| M2.1 | **Master at the end:** Master and the safety limiter move after Post, in Serial and Parallel (Master leaves the `[MIX]` gains); the MIXER screen gets an OUT page (Master) and `[MIX]` page 1 becomes Crossfade / Curve. Mixer-only edits are saved on a patch change with AUTO SAVE (now lost: the load routine's stock dirty check at `0xC00B892C` can't be hooked, so `unpack_live` sets up the same save when only the mixer settings differ: the load routine itself has no AUTO SAVE check, so mixer edits follow whatever stock does with its own edits); a MIXER screen knob edit marks the patch edited and starts the AUTO SAVE timer like a stock edit (the CC path already does). Saving follows stock in every case: STORE, AUTO SAVE timer, patch change with AUTO SAVE, nothing at power-off | Master turns down Post effects too; mixer-only edits survive a footswitch / MIDI PC patch change | Sonnet, Opus review |
| M2.2 | **Levels:** Input Level moves to an IN page and acts on the input in every mode (before Pre); Input, the four bus levels and Master go 0-150 (100 = unity, CCs scaled to 150); a `LIMIT` tag on the OUT page while the limiter reduces gain | boost a quiet chain; LIMIT shows when it bites | Sonnet |
| M3 | Split in three: | | |
| M3a | **A bus for every slot**, saved per patch (byte 17 of each packed slot block), that follows the effect when the stock Effect Chain screen moves it, or an effect is added or deleted; a temporary MIXER screen page pair BUS 1/2, BUS 2/2 sets it; old patches load as Serial, every effect Pre | stock effects on Bus A / B, kept across STORE and power-off, following moves | Opus |
| M3b | **Effect Chain screen** rebuilt as in the official mockup [`mixer-ui-mockup.html`](mixer-ui-mockup.html) (two rows, nodes, signal lines, A/B tags in Effect View, add / change type / delete, DSP FULL); replaces the BUS pages. Also the **PEDAL INPUT** setting itself: a 9th SETTINGS row (MONO INPUT / STEREO INPUT, ENTER flips it, saved in bit 7 of byte 23 of record 50; `asm/mixer/pedal_in.c` through the screen 1 table entries and the settings.S pack/unpack trampolines, because settings.S has no room left in L2). **Test build 2026-10-19, static checks only** (section "M3b test build") | the new screen | Sonnet, Opus review |
| M3c | **PEDAL INPUT** acts (MONO hides Split input and Mono Serial, draws one IN), Split modes, Mono Serial, Output Mode, Mute / Solo, jack L / R levels (Input L / R, Master L / R) | the rest of the design | Sonnet, Opus review |
| M4 | Smart Warning, checked live on the pedal (no effect types table, so it works for any ZDL): while playing, the engine compares each slot's L and R in and out; stereo in but identical L / R out means the effect collapsed it to mono. Bus latency matching dropped (Luca, 2026-10-22: effects run on the same block, gain too small) | badges | later |

Each step ends with tests, a real build from Zoom's MS-70CDR updater and a
flash test by Luca before the next one starts, as in the 70CDR port.

## Decided (Luca, 2026-10-18)

- Master Level always acts at the very end of the chain, after Post. It moves
  from `[MIX]` to the OUT jack's page; Output Mode stays on `[MIX]`, where
  Split splits the buses (M3; the MIXER screen
  gets an OUT page in M2.1).
- The safety limiter (automatic, no setting) is the last thing before the
  jacks, in Serial and Parallel.
- Mixer-only edits must not be lost on a patch change with AUTO SAVE.
- DSP FULL keeps the stock rule in M3; a higher limit is a later, measured feature.
- Input Level gets its own IN page and sets the input level in every mode.
- Every level goes to 150, like stock effects.
- The limiter shows a `LIMIT` tag over the OUT jacks in the Effect Chain screen.
- No Phase Invert A.
- Nodes and jacks open only from the Effect Chain screen, not in Effect View. EXIT returns to it.
- IN and OUT get L/R levels in Split (Input L / R, Master L / R), M3c.

## Decided (Luca, 2026-10-15)

- M2 is tried with a routing probe ZDL (sound source, filter, delay, BUS knob),
  several in one patch, before the new Effect Chain screen.
- Parallel and Serial in M2; Split input, Split output and PEDAL INPUT in M3.
- Old patches load as Serial with every effect in Pre.
- M0 starts now.

## M1 test build (2026-10-16)

`patches/mixer-m1.yaml` (source `asm/mixer/`): the engine at DDR `0xC00F6000`, layout fixed at
section +32, slot 0 first: **PRE PRE A B POST POST**. On screen (signal flows right to left):
the 2 rightmost effects are Pre, the 3rd from the right is Bus A, the 4th is Bus B, the 2
leftmost are Post. MIX is 50/50, no limiter yet (a 50/50 sum is never louder than the louder
bus; the limiter comes with the M2 levels). With positions 3 and 4 empty both buses carry the
same signal, so it sounds like stock. The probe's P1 is in the build (`m0-probe.yaml`), its
slot-loop hook (`m0-probe-chain.yaml`) is not: same packet, so P1's FX row and P3 read 0.

`zoomms build <MS-70CDR 2.10 updater> --build-id ms70cdr-2.10 --patch patches/version-1.2.yaml
--patch patches/boot-logo.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml
--patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml --patch patches/scroll.yaml
--patch patches/m0-probe.yaml --patch patches/mixer-m1.yaml --stamp "label=M1 MIXER"
--out "build/out/MIDISTOMP M1 mixer.exe"`

Assembled locally with TI's `cl6x` (CGT 8.5, the source has no macros); GNU binutils is
still the reference (`tests/test_mixer_patch.py`, skipped without it).

**Pedal results (Luca, MS-70CDR, 2026-10-16): works.** Stock-equal with positions 3-4 empty,
parallel drive + chorus/delay heard side by side, effect change and CC 80/81 switches without
clicks.

| patch | declared DSP | BLK min / avg / max | LOAD avg / max | PEAK |
|---|---|---|---|---|
| empty | 0 | 5 228 / 5 291 / 7 038 | 9 % / 12 % | 15 % |
| heavy (Arena, LO-FI Dly, FuzzSmile, Air, StonePha, LOFI Rev) | 293.4 | 32 018 / 35 316 / 42 126 | 64 % / 77 % | 83 % |

- Engine cost is lost in the noise: empty-patch PER AVG 12 204 vs 12 005 in probe v1.
- About **100 cycles per declared unit** ((35 316 - 5 291) / 293.4 = 102; probe v1 gave 95).
- At 293 declared the worst block still had 23 % headroom, so the stock 225 limit is very
  conservative. The final limit is still open (handoff "Later").
- ICE Delay and AnalogDly write F on every slot (probe v2 P6, 2026-10-18), so copying F routes
  them. Their F0 in probe v1 is not reproduced. Gyre is not checked.

## M2 test build (2026-10-16)

`patches/mixer-m2.yaml` replaces mixer-m1 (source `asm/mixer/`, the vectors and data offsets
are at the top of `mixer.S`).

**Pedal results (Luca, MS-70CDR, 2026-10-18): works.** Round 1 had two bugs: saving (the
live-save buffer is `0xC009C2A8`, not `0xC008C2A8`, so STORE wrote no settings and its reload
showed the defaults) and Master in Serial. Round 2 fixed both, plus the load routine's auto save
of the patch it leaves (`0xC00B89F4`, now gets PREV); all six round 2 steps pass.

- **Settings** (11 bytes + a magic byte): Mode (Serial / Parallel), Send, Input Level, Route A
  and B levels, Crossfade, Master, Curve (Smooth = equal power, DJ = Send law, Cut), Mix A and
  B levels, Phase Invert B. Serial runs the six slots in order, like stock, then
  Master. Gains are smoothed
  per block; a block-rate limiter (0.98 ceiling) sits after MIX.
- **Buses** come from `RoutePrb` (effects pack, `src/probes/routeprb`): its Bus knob writes
  `0x80 | bus` into MAIL[slot] (`0xC00F6088`) every block; the engine latches it and clears
  MAIL, so a removed probe falls back to Pre. Stock effects stay in Pre until M3. (M2 only: M3a sets buses on the MIXER screen and drops RoutePrb.)
- **Saved per patch:** since M3b7, settings 0-10 live in a 16-byte entry per patch in
  record 50 (the globals record, grown 24 -> 824 B), keyed by a hash of the patch's effect ids
  and name. Settings 18-23 (bus, output mode, mute, solo) stay in byte 17 of the slot blocks.
  (M3b5/6 used bytes 14/15, the high bits of P8, and broke effects with a wide knob 8; their
  patches are read once and P8 is cleared.) Hooks:
  the live and saved-copy unpacks, the editor dump pack, REC_SAVE (`0xC00B84C0`, every save) and
  IS_DIRTY (four call sites; AUTO SAVE's goes through tempo-hold's `dirty_hook`). A patch
  without the magic loads the defaults (Serial). Not hooked: the compact IS_DIRTY call in patch
  load (`0xC00B892C`), so a patch change with only mixer edits pending skips that save prompt;
  AUTO SAVE still saves them.
- **Screen:** MENU > MIXER (stock-unused screen 15), 4 pages of 3 knobs, knob 1 press = page.
- **CCs** (follow CC RECEIVE and MIDI CHANNEL, 0-127 scaled to the range): 85 Send,
  86 Crossfade, 87 Master, 88 Input Level, 89 Route A, 90 Route B, 91 Mix A, 92 Mix B, 93 Mode,
  94 Curve, 95 Phase Invert B, 96 Input R, 97 Master R, 98 Output Mode, 99 Mute A, 100 Mute B,
  101 Solo. 88 Input also sets Input R unless Split (input), 87 Master also sets Master R unless
  Split (output), as the knobs. 96-101 clash with nothing (chart 14-73, stock 74/75, 80/81). Go in `docs/user-guide.md` section 5 when the mixer ships.

Build: as M1 with `--patch patches/mixer-m2.yaml --stamp "label=M2 MIXER"`.

## M2.1 test build (2026-10-18)

Master and the limiter at the chain's end in both modes, the OUT page, MIXER knob edits mark
the patch edited, mixer-only edits saved on a patch change by the load routine's own save
(`unpack_live`). **Pedal results (Luca, 2026-10-18): all steps pass.**

## M2.2 test build (2026-10-18)

Input Level on its own IN page, applied to the input in both modes (before Pre); Input, the
four bus levels and Master go 0-150 (CCs scale 0-127 to 0-150, so unity is CC 84); a LIMIT tag
on the OUT page, redrawn by a poll chained in front of midi-clock's (its trampoline at
`0xC00C82D0` now jumps to the mixer's vector +120, `asm/mixer/poll_trampoline.S`).
**Pedal results (Luca, 2026-10-18): all steps pass.**

## M3a test build (2026-10-18)

Every slot has a bus (PRE / A / B / POST), saved per patch in byte 17 of its packed slot block
(stock packs it as 0 and never unpacks it, research doc section 6); bits 2-7 stay 0 for M3c.
It travels with the 12 setting bytes through every M2 save path (STORE, AUTO SAVE, the patch
change's own save, editor dump / store), and a bus-only edit marks the patch edited. A patch
without the Mixer magic loads Serial with every bus PRE.

- **Set it:** MENU > MIXER, two more pages **BUS 1/2** (S1 S2 S3) and **BUS 2/2** (S4 S5 S6),
  S1 = the rightmost effect. Temporary, until M3b; no CC (M3b decides).
- **It follows the effect:** the stock Effect Chain screen's lift-and-move, add (hold the cursor,
  pick a type: the new effect joins the bus of the effect it was added next to) and delete
  (the effects above move down with their buses, the last slot gets PRE). Hooks and evidence:
  [mixer-mode-m3-research.md, "M3a hooks"](mixer-mode-m3-research.md#m3a-hooks-2026-10-18-ti-dis6x-of-the-whole-210-os-image).
- **RoutePrb** is no longer read (dropped after M3a, 2026-10-18): the engine's MAIL latch is
  gone and the 8 MAIL bytes at +136 are unused.

**Pedal results (Luca, MS-70CDR, 2026-10-18): works.** All test steps pass: buses save and
reload, follow move / add / delete, survive AUTO SAVE. Luca's theory, unmeasured: past the
DSP limit the audio cuts out.

## M3b test build (2026-10-19)

The stock Effect Chain screen (MENU > EFFECT CHAIN, screen 3) is replaced by the mockup's
([`mixer-ui-mockup.html`](mixer-ui-mockup.html) v20): `asm/mixer/chain_keys.c` (model, keys,
hooks) and `chain_draw.c` (pixels), C built with TI cl6x into a section at `0xC00F8000`
(`py scripts/build_mixer_ui.py --write` regenerates both sections' hex). Addresses and evidence:
[mixer-mode-m3-research.md, "M3b"](mixer-mode-m3-research.md#m3b-the-new-effect-chain-screen-2026-10-19-ti-dis6x-of-the-210-os).
The MIXER screen's BUS pages are gone (6 pages again); buses are set here.

- **Browse:** knob 1 walks IN, Pre, `[ROUTE]`, one bus row, `[MIX]`, Post, OUT; knob 3 jumps
  to the other bus row (Parallel).
- **Select** (knob 1 press, not on the jacks), then knob 1 moves it: an effect within its zone,
  then across `[ROUTE]` / `[MIX]` (Pre ↔ A, A / B ↔ Post); a node takes the effect next to it.
  Knob 3 on a selected effect: A ↔ B; on `[ROUTE]`: Mode Serial / Parallel.
- **OPEN** (knob 3 press): an effect's stock knob pages, a node's or jack's MIXER pages (IN,
  ROUTE 1-2, MIX 1-2, OUT only); EXIT from MIXER pages comes back here, from an effect it is
  stock (the patch list).
- **Add:** hold cursor left / right: stock's type list (screen 33), then back here with the
  new effect on the zone the mockup gives it and the cursor on it. Cursor up / down: type.
- **Delete:** select an effect, hold knob 2 (0.6 s): DELETE?, then press knob 2; anything
  else cancels.
- **EXIT** (knob 2, nothing selected): the menu, as stock.

**Status: static checks only, not pedal-tested.** `py -m pytest -q` checks the hooks against
the stock image, the C section's place and vectors, and that a fresh TI build (no RTS, no
B14) equals the yaml hex. The footswitch on this screen works (Luca, 2026-10-23). Not done: DSP FULL
popups, `[MIX]` Output Mode (M3c).

Pedal checks: every key above; LIMIT tag over OUT; a long chain move (4 swaps) in Parallel
for clicks; EXIT from MIXER pages / the add list lands back on the chain (an opened effect's EXIT is stock: the patch list) with
the same cursor.

## M3c test build (2026-10-19, M3b4)

PEDAL INPUT now acts, and the MIXER screen (15) is the node knob pages of the brief
("Node knob pages"), drawn like stock effect pages (`pages.c` model, `chain_draw.c`
`pages_draw`): IN 1 page, `[ROUTE]` 2, `[MIX]` 3, OUT 1; knob 3 press walks the pages of the
node opened (MENU > MIXER: all 7), EXIT back to the chain or the menu.

- **Engine in C** (`engine.c`, called from the mixer.S stub): Serial, Parallel, Split,
  Mono Serial; `[MIX]` crossfade curves Smooth / DJ / Cut, Mix A / B, Phase B, Mute / Solo,
  Output Stereo / Mono / Split; Input and Master L / R; the limiter.
- **Settings:** 24 bytes (18-23: Input R, Master R, Output, Mute A, Mute B, Solo), packed in
  byte 17 bits 2-7 of the six slot blocks (`mix_get` / `mix_put`); older patches read as
  unity / Stereo / Off.
- **MONO input:** Split plays as Parallel, Mono Serial as Serial; the Mode knob and CC Mode
  stop at Parallel. **STEREO:** the chain screen draws the double lines and the mode icons.

**Status: static checks only, not pedal-tested.** pytest checks the data block, the vectors
and that a fresh TI build equals the yaml hex; host PNGs of the chain and pages match the
mockup. The A/B tag in Effect View is in the build. Smart Warning is postponed to after v2.0 (Luca, 2026-10-23).

## M3b8 pedal test (2026-10-22)

M3b8 = M3b7 (settings 0-10 in record 50, byte 17 only in the patch) + both crossfades shown
pan-style (A100 .. AB .. B100, "-" when inactive). Luca ran the M3b7 steps and the M3b8
steps on M3b8: **all pass** (knob 8 kept, mixer settings per patch through patch change and
power-cycle, globals kept, copy, dirty mark, crossfade text and sides, "-", saved B30, fit).
One fail: **[ROUTE] XFade drew as a knob**, not a fader like [MIX] XFade. Fixed in
**M3b9** (`pages.c`: S_SEND is a FADER), sha256 31ebfd37...: **pedal-tested, pass** (Luca, 2026-10-22).
