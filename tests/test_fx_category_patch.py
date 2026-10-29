import importlib.util
from pathlib import Path

import pytest

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/fx-category.yaml")
SEC = PATCH["section"][0]
W = {w["addr"]: w for w in PATCH["write"]}


def _data(d):
    return bytes.fromhex("".join(d.split()))


def _word(h):
    return int.from_bytes(bytes.fromhex(h), "little")


def _disp(addr, h):
    """Target of a callp / b with a 21-bit word displacement."""
    d = (_word(h) >> 7) & 0x1FFFFF
    return (addr & ~31) + 4 * (d - (1 << 21) if d & (1 << 20) else d)


def _mvk_pair(lo, hi):
    return ((_word(hi) >> 7) & 0xFFFF) << 16 | (_word(lo) >> 7) & 0xFFFF


def _words(code, i, n):
    return [int.from_bytes(code[k:k + 4], "little") for k in range(i, i + 4 * n, 4)]


def test_data_is_the_ms50g_screen():
    code = _data(SEC["data"])
    assert code[156] & 1 == 0                                         # no p-bit chains data into draw
    assert _words(code, 0, 6) == [1, 3, 4, 6, 8, 0]                   # tbl, as MS-50G 0xC00ECF80; [5] EXIT
    assert _words(code, 24, 6) == [1, 43, 85, 1, 43, 85]              # xs, as MS-50G 0xC00ECE50
    assert _words(code, 48, 6) == [10, 10, 10, 36, 36, 36]            # ys, as MS-50G 0xC00ECE68
    nxt, prv = _words(code, 72, 6), _words(code, 96, 6)
    assert [prv[n] for n in nxt] == list(range(6))                    # prev undoes next
    c, seen = 0, []
    for _ in range(6):
        seen.append(c)
        c = nxt[c]
    assert seen == [0, 3, 1, 4, 2, 5]                                 # column-wise, as the MS-50G
    assert code[120:160] == b"OD/ DIST\0AMP\0MOD/SFX \0DLY/REV \0DYN/FLTR\0"  # MS-50G 0xC00E967E strings


def test_writes_point_at_the_section():
    a = SEC["addr"]
    draw, nxt, prv, enter = a + 160, a + 256, a + 272, a + 320
    code = _data(SEC["data"])
    assert code[160:164] == bytes.fromhex("f654bc01")                 # draw: stw b3
    assert code[256:260] == bytes.fromhex("29249501")                 # next: mvkl nxt, a3
    assert code[272:276] == bytes.fromhex("28309501")                 # prev: mvkl prv, a3
    assert code[320:324] == bytes.fromhex("29009501")                 # enter: mvkl tbl, a3
    assert _disp(0xC00A90D4, W[0xC00A90D4]["expect"]) == 0xC00A0144
    assert _disp(0xC00A90D4, W[0xC00A90D4]["data"]) == draw
    assert _disp(0xC00A7B00, W[0xC00A7B00]["data"]) == enter
    assert _word(W[0xC00A7B00]["data"]) >> 28 == 0                    # unconditional
    assert _word(W[0xC00EF18C]["data"]) == prv and _word(W[0xC00EF194]["data"]) == nxt
    assert not {0xC00A7A8C, 0xC00A7A90, 0xC00A7AA8} & set(W)          # stock key table width (events 68-74)
    labels = ((0xC00A9078, 0xC00A9084, 0xC00E91E3, a + 151), (0xC00A908C, 0xC00A9094, 0xC00E91E7, a + 120),
              (0xC00A90A0, 0xC00A90A8, 0xC00E91EB, a + 129), (0xC00A90B0, 0xC00A90C0, 0xC00E91EF, a + 133))
    pairs = ((0xC00A7B20, 0xC00A7B24, 0xC00ECAC8, a), (0xC00A7BD4, 0xC00A7BD8, 0xC00ECAC8, a),
             (0xC00A912C, 0xC00A9130, 0xC00ECA68, a + 24), (0xC00A9134, 0xC00A9138, 0xC00ECA80, a + 48)) + labels
    for lo, hi, old, new in pairs:
        assert _mvk_pair(W[lo]["expect"], W[hi]["expect"]) == old
        assert _mvk_pair(W[lo]["data"], W[hi]["data"]) == new
    for x in (0xC00A90D4, 0xC00A90E0) + tuple(a for p in pairs for a in p[:2]):
        old, new = _word(W[x]["expect"]), _word(W[x]["data"])     # only the constant changes
        assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)
    assert W[0xC00A7A50]["data"] == "27c6" and W[0xC00A7A56]["data"] == "40c4"  # mod 6, MS-50G bytes


def test_section_fits_its_gap():
    assert 0xC00F29A0 <= SEC["addr"] and SEC["addr"] + len(_data(SEC["data"])) <= 0xC00F3000


def test_section_matches_a_fresh_ti_build():
    spec = importlib.util.spec_from_file_location("build_mixer_ui", ROOT / "scripts" / "build_mixer_ui.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    if not b.available():
        pytest.skip("TI CGT not installed (TI_CGT)")
    assert b.assemble(ROOT / SEC["source"], SEC["addr"]) == _data(SEC["data"])
