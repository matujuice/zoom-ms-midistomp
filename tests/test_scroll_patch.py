import re
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
def _view(p, build="ms50g-3.10"):
    """The patch as one build sees it (the tests below check the MS-50G entries;
    test_ms70cdr_port.py the MS-70CDR ones)."""
    return {k: [e for e in v if e["model"] == build] if k in ("write", "section") else v for k, v in p.items()}


ALL = patcher.load(ROOT / "patches/scroll.yaml")
PATCH = _view(ALL)
SECTION = PATCH["section"][0]


def callp_target(addr, data):
    w = int.from_bytes(bytes.fromhex(data), "little")
    disp = (w >> 7) & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp & (1 << 20) else disp)


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_section_matches_assembly_source():
    for sec in ALL["section"]:
        code = asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True, build=sec["model"])
        assert code == bytes.fromhex("".join(sec["data"].split()))


def test_call_sites_retargeted():
    sleep, right, left, bump_sleep = PATCH["write"]
    for site in (sleep, bump_sleep):
        assert callp_target(site["addr"], site["expect"]) == 0xC00CF000  # stock sleep
        assert callp_target(site["addr"], site["data"]) == SECTION["addr"]  # frame_sleep, first in scroll.S
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
