# Fonts read from the OS at run time (plan, 2026-11-07)

Jannik's review of repeat98/modwerk#1278: `asm/common/draw.h` carries three font tables copied
from Zoom's OS. Read them from the OS at run time instead, as `asm/looper/lbox.c` already does
with `FONT7` (0xC00E87D8). Then no Zoom bytes sit in our sources.

## Where they are in the stock 2.10 OS

Each table matched the stock image byte for byte (whole table, one hit):

| draw.h | Bytes | Stock address | Note |
|--------|-------|---------------|------|
| `F7`   | 665 | `0xC00E88B8` | = lbox.c's `FONT7` + 32 x 7: same font, from ASCII 32 |
| `OS6`  | 570 | `0xC00E8DA8` | 6 x 8 OS font, ASCII 32 on |
| `SOFT` | 192 | `0xC00EA9B0` | softkey font, 4 columns per glyph |

No patch writes inside these ranges. mixer-m2 writes 4 bytes at 0xC00EA9A8 (record size table,
entry 50), which end right before `SOFT`.

## Done (2026-11-07)

- `asm/common/fonts.h` defines `F7`, `OS6`, `SOFT` as the OS addresses on the pedal (`_TMS320C6X`)
  and takes `tests/host_fonts.h` on the PC (previews, README shots, tests). `scols()` and our own
  `SW_M`, `SW_W`, `SW_N`, `SW_Q` (wider M W N, and the `?` the softkey font lacks) live there.
- `asm/mixer/chain_draw.c`: the mockup's G5 / G3 (and K5 / K3) are gone. Covers and the title use
  FONT7, keys, hints and tags the softkey font, the same fonts as the rest of our pages (Luca,
  2026-11-07: use the font already on the pedal).
- It reads the font data, not the OS text call (0xC00A9C18): that writes to the LCD frame, and
  our pages draw into their own buffer first.
- Sections shrink by 3040 bytes (chain_keys.c 1088, mid 704, master 1248). No audio-path CPU
  change: only UI drawing reads the fonts.

## Test (needs the pedal)

1. Effect Chain, Mixer, Perform, Master pages: text looks as in `docs/img` (covers, title, keys,
   arrows, `DELETE?`).
2. Power-cycle, open each page again (the OS must not overwrite the tables after boot).
3. Only then: a new pin for #1278.
