from pathlib import Path

import pytest

from zoomms import ais, asm, patcher
from tests.test_ais import make_ais

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/midi-cc.yaml")


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_patch_bytes_match_assembly_source():
    for kind in ("write", "section"):
        for entry in PATCH[kind]:
            if "source" not in entry:
                continue
            code = asm.assemble(ROOT / entry["source"], entry["addr"], whole_packets=kind == "section")
            assert code == bytes.fromhex(entry["data"]), entry["source"]


def test_callsite_is_retargeted_to_trampoline():
    site, tramp = PATCH["write"]
    word = int.from_bytes(bytes.fromhex(site["data"]), "little")
    old = int.from_bytes(bytes.fromhex(site["expect"]), "little")
    packet = site["addr"] & ~31  # callp is relative to its fetch packet

    def target(w):
        disp = (w >> 7) & 0x1FFFFF
        return packet + 4 * (disp - (1 << 21) if disp & (1 << 20) else disp)

    assert target(old) == 0xC00AE0F8  # stock midi_channel_msg
    assert target(word) == tramp["addr"]
    assert word & ~(0x1FFFFF << 7) == old & ~(0x1FFFFF << 7)
    assert len(bytes.fromhex(tramp["data"])) <= 24  # the free gap


def test_other_builds_refused():
    img = ais.parse(make_ais())
    with pytest.raises(patcher.PatchError, match="only written for"):
        patcher.apply(img, PATCH, "ms60b-2.10")


def test_section_kind_adds_code():
    img = ais.parse(make_ais())
    p = {"name": "t", "section": [{"model": "m", "addr": 0x11900000, "data": "01 02 03 04"}]}
    patcher.apply(img, p, "m")
    assert ais.parse(ais.build(img)).sections[-1].data == b"\x01\x02\x03\x04"
    with pytest.raises(patcher.PatchError):
        patcher.apply(img, {"name": "t", "section": [{"model": "m", "addr": 0x11900002, "data": "00"}]}, "m")
