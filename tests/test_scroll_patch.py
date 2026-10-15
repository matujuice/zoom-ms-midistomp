import re
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/scroll.yaml")
SECTION = PATCH["section"][0]


def callp_target(addr, data):
    w = int.from_bytes(bytes.fromhex(data), "little")
    disp = (w >> 7) & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp & (1 << 20) else disp)


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_section_matches_assembly_source():
    code = asm.assemble(ROOT / SECTION["source"], SECTION["addr"], whole_packets=True)
    assert code == bytes.fromhex("".join(SECTION["data"].split()))


def test_call_sites_retargeted():
    sleep, right, left = PATCH["write"]
    assert callp_target(sleep["addr"], sleep["expect"]) == 0xC00CF000  # stock sleep
    assert callp_target(sleep["addr"], sleep["data"]) == SECTION["addr"]  # frame_sleep, first in scroll.S
    for site in (right, left):
        assert callp_target(site["addr"], site["expect"]) == 0xC00C4DCC  # stock end bump
        assert callp_target(site["addr"], site["data"]) == SECTION["addr"] + 0x1C  # wrap
    for site in PATCH["write"]:  # only the displacement changes
        old, new = (int.from_bytes(bytes.fromhex(site[k]), "little") for k in ("expect", "data"))
        assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)


def test_frame_times():
    src = (ROOT / SECTION["source"]).read_text()
    frame, wrap = (int(re.search(rf"\.equ\s+{n},\s*(\d+)", src).group(1)) for n in ("FRAME_MS", "WRAP_MS"))
    assert 0 < frame < 100 and 0 < wrap < 100  # faster than stock
