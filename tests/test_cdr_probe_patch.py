from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PROBE = patcher.load(ROOT / "patches/cdr-probe.yaml")
LOOPER = patcher.load(ROOT / "patches/looper.yaml")


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    (site,), (sec,) = PROBE["write"], PROBE["section"]
    assert asm.assemble(ROOT / site["source"], site["addr"]).hex() == site["data"]
    code = asm.assemble(ROOT / sec["source"], sec["addr"], whole_packets=True)
    assert code == bytes.fromhex("".join(sec["data"].split()))


def test_chains_after_looper_and_fits_below_the_services_block():
    (site,), (sec,) = PROBE["write"], PROBE["section"]
    assert site["addr"] == LOOPER["write"][0]["addr"] and site["expect"] == LOOPER["write"][0]["data"]
    hooks = LOOPER["section"][0]
    assert sec["addr"] >= hooks["addr"] + len(bytes.fromhex("".join(hooks["data"].split())))
    assert sec["addr"] + len(bytes.fromhex("".join(sec["data"].split()))) <= 0xC00F3000
