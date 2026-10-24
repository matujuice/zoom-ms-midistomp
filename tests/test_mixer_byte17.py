"""Settings 18-23 in byte 17 of each slot block (asm/mixer/pages.c mix_put / mix_get), mirrored in Python:
they come back unchanged, and bit 7 stays 0 (a SysEx round trip moved it into other bytes, issue 48)."""
import itertools
from pathlib import Path

PAGES = (Path(__file__).resolve().parent.parent / "asm/mixer/pages.c").read_text()


def put(inr, mr, out, ma, mb, solo, bus=3):
    w = (inr ^ 100) | (mr ^ 100) << 8 | out << 16 | ma << 18 | mb << 19 | solo << 20
    rec = [bus | (w >> 5 * i & 31) << 2 for i in range(6)]
    rec[5] |= 0x40
    return rec


def get(rec):
    v2, w = rec[5] >> 6 & 1, 0
    for i in range(6):
        w |= (rec[i] >> 2 & 31) << 5 * i if v2 else (rec[i] >> 2) << 6 * i
    return (w & 255) ^ 100, (w >> 8 & 255) ^ 100, w >> 16 & 3, w >> 18 & 1, w >> 19 & 1, w >> 20 & 3


def test_mirror_matches_pages_c():
    for line in ("rec[18 * i + 17] = (src[12 + i] & 3) | (w >> 5 * i & 31) << 2;", "rec[18 * 5 + 17] |= 0x40;",
                 "int v2 = rec[18 * 5 + 17] >> 6 & 1;", "(unsigned)(rec[18 * i + 17] >> 2 & 31) << 5 * i",
                 "(unsigned)(rec[18 * i + 17] >> 2) << 6 * i"):
        assert line in PAGES, line


def test_round_trip_keeps_bit_7_clear():
    for t in itertools.product(range(256), range(0, 256, 5), range(4), (0, 1), (0, 1), range(4)):
        rec = put(*t)
        assert all(b < 0x80 for b in rec) and get(rec) == t, t


def test_stock_and_old_saves():
    assert get([0] * 6) == (100, 100, 0, 0, 0, 0)           # stock patch: the defaults
    w = (80 ^ 100) | (90 ^ 100) << 8 | 2 << 16 | 1 << 20    # a save in the old 6-bit layout
    assert get([(w >> 6 * i & 63) << 2 for i in range(6)]) == (80, 90, 2, 0, 0, 1)
