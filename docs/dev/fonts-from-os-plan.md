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

## Change

All uses only take a pointer (`F7 + 7 * code(c)`, `OS6 + 6 * ...`, `SOFT + 4 * i`; one more in
`perform_draw.c:42`), so the arrays become defines:

    #define F7   ((const unsigned char *)0xC00E88B8)
    #define OS6  ((const unsigned char *)0xC00E8DA8)
    #define SOFT ((const unsigned char *)0xC00EA9B0)

`SW_M`, `SW_W`, `SW_N` (our wider M W N) stay: they are ours. The sections shrink by 1427 bytes.
MS-50G / MS-60B builds don't use draw.h today; if they ever do, they need their own addresses.

## G5 / G3 (`asm/mixer/chain_draw.c`)

Row bitmaps (5 x 7 and 3 x 5) from the mixer mockup, a different format from the OS fonts.
Waiting on Luca: did he draw them, or copy them from Zoom's screens? If drawn, they stay and we
say so in the reply. If copied, find them in the OS the same way and read them from there.

## Test (needs the pedal)

1. Build the release with the defines; the Perform, Master and Effect Chain pages must look the
   same as before (compare against `scripts/screens` shots).
2. Power-cycle, open each page again (the OS must not overwrite the tables after boot).
3. Only then: a new pin for #1278.
