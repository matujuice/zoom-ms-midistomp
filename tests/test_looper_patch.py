from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/looper.yaml")
HOOKS, BLOCK = PATCH["section"]


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    for site in PATCH["write"]:
        if "source" not in site:
            continue
        assert asm.assemble(ROOT / site["source"], site["addr"]).hex() == site["data"]
    for sec in PATCH["section"]:
        code = asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True)
        assert code == bytes.fromhex("".join(sec["data"].split()))


def far_target(data):
    """mvkl/mvkh .S2 target, b0: the 16-bit constants sit in bits 7-22."""
    lo, hi = (int.from_bytes(bytes.fromhex(data)[i:i + 4], "little") >> 7 & 0xFFFF for i in (0, 4))
    return hi << 16 | lo


def test_trampolines_go_to_the_hook_vectors():
    poll, toggle, hold, cc, draw = PATCH["write"]
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


def test_draw_callsite_goes_to_draw_pre():
    draw = PATCH["write"][4]
    assert draw["addr"] == 0xC00BB0EC
    assert callp_target(draw["addr"], draw["expect"]) == 0xC00D5720
    assert callp_target(draw["addr"], draw["data"]) == HOOKS["addr"] + 32
    old, new = (int.from_bytes(bytes.fromhex(draw[k]), "little") for k in ("expect", "data"))
    assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)  # still callp .S2 b3, parallel bit kept


def test_block_layout():
    data = bytes.fromhex("".join(BLOCK["data"].split()))
    word = lambda off: int.from_bytes(data[off:off + 4], "little")
    assert BLOCK["addr"] == 0xC00F3000 and len(data) == 128
    assert word(0) == 0x5A4C5301 and word(4) == 3
    regions = [(word(8 + 8 * k), word(12 + 8 * k)) for k in range(3)]
    assert regions == [(0xC0636980, 0xC07D0000 - 0xC0636980),   # RAM test region 3
                       (0xC0198000, 0xC0200000 - 0xC0198000),   # region 2
                       (0xC0102000, 0xC0198000 - 0xC0102000)]   # region 1 above 64 KB of code
    assert word(40) == 0xFFFFFFFF  # no slot claimed
    hooks_end = HOOKS["addr"] + len(bytes.fromhex("".join(HOOKS["data"].split())))
    assert hooks_end <= BLOCK["addr"]
