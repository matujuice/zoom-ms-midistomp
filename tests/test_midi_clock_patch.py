from pathlib import Path

import pytest

from zoomms import ais, asm, patcher
from tests.test_ais import make_ais

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/midi-clock.yaml")
CC = patcher.load(ROOT / "patches/midi-cc.yaml")


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_patch_bytes_match_assembly_source():
    for kind in ("write", "section"):
        for entry in PATCH[kind]:
            if "source" not in entry:
                continue
            code = asm.assemble(ROOT / entry["source"], entry["addr"], whole_packets=kind == "section")
            assert code == bytes.fromhex(entry["data"]), entry["source"]


@pytest.mark.parametrize("pair", [0, 2])
def test_hook_calls_trampoline(pair):
    site, tramp = PATCH["write"][pair:pair + 2]
    word = int.from_bytes(bytes.fromhex(site["data"]), "little")
    packet = site["addr"] & ~31  # callp is relative to its fetch packet
    disp = (word >> 7) & 0x1FFFFF
    disp = disp - (1 << 21) if disp & (1 << 20) else disp
    assert packet + 4 * disp == tramp["addr"]
    assert word & 0x7F == 0x12 and word >> 28 == 1  # callp .S2, p-bit clear
    assert len(bytes.fromhex(tramp["data"])) <= 16  # the free gap


def test_no_overlap_with_midi_cc_patch():
    def spans(p):
        for e in p.get("write", []) + p.get("section", []):
            yield e["addr"], e["addr"] + len(bytes.fromhex(e["data"]))
    ours = list(spans(PATCH))
    for a, b in spans(CC):
        for c, d in ours:
            assert b <= c or d <= a
    secs = sorted(PATCH["section"], key=lambda e: e["addr"])
    for a, b in zip(secs, secs[1:]):
        assert a["addr"] + len(bytes.fromhex(a["data"])) <= b["addr"]
    assert secs[-1]["addr"] + len(bytes.fromhex(secs[-1]["data"])) <= 0x11820000  # end of L2


def test_transport_block():
    block = bytes.fromhex(PATCH["section"][-1]["data"])
    assert PATCH["section"][-1]["addr"] == 0x1181FF00  # published to the effects pack
    assert int.from_bytes(block[:4], "little") == 0x5A4D5401
    assert int.from_bytes(block[20:24], "little") == 12000


def test_other_builds_refused():
    img = ais.parse(make_ais())
    with pytest.raises(patcher.PatchError, match="only written for"):
        patcher.apply(img, PATCH, "ms60b-2.10")
