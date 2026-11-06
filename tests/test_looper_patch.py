import importlib.util
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/looper.yaml")
HOOKS, BLOCK, LBOX = PATCH["section"]


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    for site in PATCH["write"]:
        if "source" not in site:
            continue
        assert asm.assemble(ROOT / site["source"], site["addr"]).hex() == site["data"]
    for sec in (HOOKS, BLOCK):                      # LBOX is C: test_lbox_matches_a_fresh_ti_build
        code = asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True)
        assert code == bytes.fromhex("".join(sec["data"].split()))


def far_target(data):
    """mvkl/mvkh .S2 target, b0: the 16-bit constants sit in bits 7-22."""
    lo, hi = (int.from_bytes(bytes.fromhex(data)[i:i + 4], "little") >> 7 & 0xFFFF for i in (0, 4))
    return hi << 16 | lo


def test_trampolines_go_to_the_hook_vectors():
    poll, toggle, hold, cc, draw, cover = PATCH["write"]
    assert far_target(poll["expect"]) == 0x1181E800  # poll.S
    assert far_target(toggle["expect"]) == 0x1181FA98  # hold.S toggle_hook
    assert far_target(hold["expect"]) == 0x1181FF20  # hold2.S hold_hook
    assert far_target(cc["expect"]) == 0xC00F2800  # midi_cc handler.S (DDR)
    for i, site in enumerate((poll, toggle, hold, cc)):
        assert far_target(site["data"]) == HOOKS["addr"] + 8 * i


def callp_target(addr, data):
    word = int.from_bytes(bytes.fromhex(data), "little")
    disp = word >> 7 & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp >> 20 else disp)


def test_draw_callsite_goes_to_the_status_bar():
    draw = PATCH["write"][4]
    assert draw["addr"] == 0xC00BB0EC
    assert callp_target(draw["addr"], draw["expect"]) == 0xC00D5720
    assert callp_target(draw["addr"], draw["data"]) == LBOX["addr"] == 0xC00F5400
    old, new = (int.from_bytes(bytes.fromhex(draw[k]), "little") for k in ("expect", "data"))
    assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)  # still callp .S2 b3, parallel bit kept


def test_cover_callsite_goes_to_lbox_cover():
    cover = PATCH["write"][5]
    assert cover["addr"] == 0xC00BAA40
    assert callp_target(cover["addr"], cover["expect"]) == 0xC00AA3D8
    assert callp_target(cover["addr"], cover["data"]) == LBOX["addr"] + 8
    old, new = (int.from_bytes(bytes.fromhex(cover[k]), "little") for k in ("expect", "data"))
    assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)


def test_block_layout():
    data = bytes.fromhex("".join(BLOCK["data"].split()))
    word = lambda off: int.from_bytes(data[off:off + 4], "little")
    assert BLOCK["addr"] == 0xC00F3000 and len(data) == 128
    assert word(0) == 0x5A4C5301 and word(4) == 3
    regions = [(word(8 + 8 * k), word(12 + 8 * k)) for k in range(3)]
    assert regions == [(0xC0636980, 0xC07D0000 - 0xC0636980),   # RAM test region 3
                       (0xC0198000, 0xC0200000 - 0xC0198000),   # region 2
                       (0xC0118C00, 0xC0198000 - 0xC0118C00)]   # region 1 above MOD code, MASTER and record 50
    assert word(40) == 0xFFFFFFFF  # no slot claimed
    hooks_end = HOOKS["addr"] + len(bytes.fromhex("".join(HOOKS["data"].split())))
    assert hooks_end <= BLOCK["addr"]


def _data(sec):
    return bytes.fromhex("".join(sec["data"].split()))


def test_lbox_matches_a_fresh_ti_build():
    spec = importlib.util.spec_from_file_location("build_looper_ui", ROOT / "scripts" / "build_looper_ui.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    if not b.available():
        pytest.skip("TI CGT not installed (TI_CGT)")
    assert b.build() == _data(LBOX)                                  # also: no RTS, no B14, below mixer.S


def test_lbox_fits_between_m0_probe_and_mixer():
    probe = patcher.load(ROOT / "patches/m0-probe.yaml")["section"]
    mixer = patcher.load(ROOT / "patches/mixer-m2.yaml")["section"]
    lo, hi = LBOX["addr"], LBOX["addr"] + len(_data(LBOX))
    for sec in probe + mixer:
        a = sec["addr"]
        assert a + len(_data(sec)) <= lo or hi <= a, hex(a)


def test_lbox_reads_the_cursor_at_draw_time():
    # S_MINE lags the screen by one poll, and 0xC00EE948 is not the cursor's slot table:
    # either put the bar on other effects' covers
    src = (ROOT / "asm/looper/lbox.c").read_text(encoding="utf-8")
    assert "SV(S_MINE) &&" not in src and "CURSOR_SLOT[6 * v + c] == SV(S_SLOT)" in src
    assert "0xC00EE748" in src and "0xC00EE948" not in src


def test_lbox_reads_the_knob_page_flag_as_one_word():
    # stock reads 0xC009D398 as one word (0xC00BAA2C); indexed by view the bar drew over knob pages
    src = (ROOT / "asm/looper/lbox.c").read_text(encoding="utf-8")
    assert "!KNOBS" in src and "VIEW_KNOBS[" not in src
