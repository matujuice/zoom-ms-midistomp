# Effect IDs and the category screen: open topic for after v2.0

v2.0 ships the MS-50G 3.10 category screen as it is (`asm/fx_category/fxcat.S`, `patches/fx-category.yaml`):
DYN/FLTR, OD/DIST, AMP on top, MOD/SFX, DLY/REV, EXIT below. The pack effects keep their beta1 IDs, so they
all sit under DLY/REV. Luca: "in the future it's an open topic to rework how the effect ids are done and how
the effect category selection works." This page collects what is known so far. Nothing here is decided.

## What we know from the MS-50G code

- The category screen code is the same on the MS-50G 3.10 and the MS-70CDR 2.10 OS; only the data differs.
  fx-category swaps the data and keeps the code.
- MS-50G data: the gid table at 0xC00ECF80 (1, 3, 4, 6, 8), the cursor x / y tables at 0xC00ECE50 / 0xC00ECE68,
  the label strings from 0xC00E967E, the cursor wraps mod 6 (two instruction bytes at 0xC00A7A50 / 56), and
  ENTER on cursor 5 (`cmpeq 5`) is EXIT.
- The stock MS-70CDR screen has 5 spots (CHO, DLY, REV, DYN/FLTR, EXIT); its OS only holds those strings.
- One gid per spot. ENTER puts the first effect of that gid in the unit; the effect knob then scrolls on
  through the whole sorted list. That is why filters follow DYN, SFX follow MOD and reverbs follow DLY: the
  screen has no spot for them.
- ENTER on a gid with nothing loaded would put effect 0 in the unit; fx-category checks the count
  (0xC00CA5F8) first and does nothing.

## Why moving an effect breaks saved patches

A patch stores each unit as its effect ID and group (gid), packed in one word:
`((fxid & 0x3F) << 17) | (((fxid >> 6) & 1) << 30) | (((fxid >> 7) & 7) << 8) | (gid << 1)`
(10 bits of ID, so at most 1023). The pedal finds the effect by that pair. Give an effect a new ID or a new
group and every patch saved with the old pair no longer finds it: the unit comes up empty. So any rework
needs a migration (rewrite the patches) or has to keep the old pairs working.

Today all pack effects are in Delay (gid 8), IDs 480-497 and 501 (beta1).

## Idea 1: six categories, knob 2 exit

Tried for beta2, then dropped for v2.0. The MS-50G grid with six real categories and no EXIT spot, the knob 2
press leaves the screen:

    DYN/FLTR   DRV   AMP
    MOD        DLY   REV

With new groups, the pack effects would go:

| Spot | Pack effects |
|---|---|
| DYN/FLTR | LOUDER, Gooey, DJFilter, EuGate, Breather |
| DRV | DirtBox, WaveFold |
| AMP | (none; amps only if loaded from an MS-50G / MS-60B set) |
| MOD | Takeoff, Choral, SGNL, DualShft, Sweep |
| DLY | GRDLOOP, GRDELAY, DubSiren, Scrub |
| REV | Washout |

The code for this was written and passed the emulator (the key jump table was widened to take event 65,
the knob 2 release).

## Idea 2: a scrollable grid in the effect chain style

A grid that scrolls like the effect chain screen, so it can hold more categories than six. Mock-ups, drawn by
the firmware's own drawing code (`asm/mixer/chain_draw.c`):

- `C:\Users\lucam\OneDrive\Documenti\CLAUDE\effect-select-scroll-first.png`
- `C:\Users\lucam\OneDrive\Documenti\CLAUDE\effect-select-scroll-middle.png`
- `C:\Users\lucam\OneDrive\Documenti\CLAUDE\effect-select-scroll-end.png`

## Idea 3: a 900+ ID range for pack effects

Give every pack effect an ID from 900 up, clear of every stock ID, with the group that matches what it does.
The list that was proposed (900-916, in this order): LOUDER, Gooey, DJFilter, EuGate, Breather (DYN);
DirtBox, Wavefold (DRV); Takeoff, Choral, SGNL, DualShft, Sweep (MOD); GRDLOOP, GRDELAY, DubSiren, Scrub
(DLY); Washout (REV). It breaks every beta1 patch with a pack effect (see above), which is why v2.0 went back.

## Finding the stock IDs

- Effect Manager's effect data file (`efx_1_30.dat`) is an encrypted zip, so the ID list can't be read from it.
- Reading the IDs back from a pedal (load each effect, read the patch over SysEx) is the easier route.
- The effects repo (zoom-ms-zdl-effects-pack) keeps the ID table: `docs/EFFECT-IDS.md` and `effect-ids.csv`.
