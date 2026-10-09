from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/ram-test.yaml")
CLOCK = patcher.load(ROOT / "patches/midi-clock.yaml")
BASE = 0xC00F1960


def _disp_target(site, data):
    w = int.from_bytes(bytes.fromhex(data), "little")
    d = (w >> 7) & 0x1FFFFF
    d = d - (1 << 21) if d & (1 << 20) else d
    return (site & ~31) + 4 * d


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_section_matches_source():
    sec = PATCH["section"][0]
    assert asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True) == bytes.fromhex(sec["data"])


def test_call_sites():
    w = {e["addr"]: e for e in PATCH["write"]}
    clock = next(e for e in CLOCK["write"] if e["addr"] == 0xC00CA630)
    assert w[0xC00CA630]["expect"] == clock["data"]  # applied on top of midi-clock.yaml
    assert _disp_target(0xC00CA630, w[0xC00CA630]["data"]) == BASE  # ram_poll
    assert _disp_target(0xC00A9434, w[0xC00A9434]["expect"]) == 0xC00A8474  # stock version draw
    assert _disp_target(0xC00A9434, w[0xC00A9434]["data"]) == BASE + 0xB0  # ram_draw
    sec = bytes.fromhex(PATCH["section"][0]["data"])
    assert sec[0xB0:0xB4] == bytes.fromhex("52e0ff07")  # addk -64, b15


def test_regions_skip_code_and_used_ram():
    sec = bytes.fromhex(PATCH["section"][0]["data"])
    words = [int.from_bytes(sec[i:i + 4], "little") for i in range(0, len(sec), 4)]
    i = words.index(0xC80F2000)
    regions = [(words[i + 3 * k], words[i + 3 * k + 1]) for k in range(5)]
    assert BASE + len(sec) <= 0xC00F2000  # code below the first region
    # the space audit's unreferenced ranges (issue #19), SDRAM through the uncached alias
    audit = [(0xC00F1958, 0xC0198000), (0xC01ADAD2, 0xC0200000), (0xC0636980, 0xC07D0000),
             (0xC07F4000, 0xC0800000), (0x80000000, 0x80020000)]
    for (s, e), (a, b) in zip(regions, audit):
        if s >> 24 == 0xC8:
            s, e = s - 0x08000000, e - 0x08000000
        assert a <= s < e <= b and s % 4 == 0
