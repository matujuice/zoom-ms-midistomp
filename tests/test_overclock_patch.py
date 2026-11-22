from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
SPEEDS = ["360f"]  # 408F failed on both test pedals (51ba9bb)


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
@pytest.mark.parametrize("speed", SPEEDS)
def test_section_matches_source(speed):
    sec = patcher.load(ROOT / f"patches/cpu-{speed}.yaml")["section"][0]
    assert asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True) == bytes.fromhex(sec["data"])


@pytest.mark.parametrize("speed", SPEEDS)
def test_jumps_to_section_then_os(speed):
    p = patcher.load(ROOT / f"patches/cpu-{speed}.yaml")
    sec, jump = p["section"][0], p["boot"][0]
    assert jump["jump"] == sec["addr"] and jump["expect"] == 0xC00DD800
    assert sec["addr"] + len(bytes.fromhex(sec["data"])) <= 0x11817000  # below MAIN's own L2 sections
