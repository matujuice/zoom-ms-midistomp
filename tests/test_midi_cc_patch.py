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

    assert target(old) == 0xC00ADF20  # stock midi_channel_msg
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


def test_handler_falls_through_to_step():
    import re
    handler, step = PATCH["section"]
    m = re.search(r"\.equ\s+STEP,\s*(0x[0-9A-Fa-f]+)", (ROOT / handler["source"]).read_text())
    assert int(m.group(1), 16) == step["addr"]
    assert step["source"] == "asm/midi_cc/step.S"


def test_cc82_taps_through_tempo_hold_trampoline():
    # No assembler needed: decode the hand-checked hex. The CC 82 branch ends
    # in mvkl/mvkh B0 + b B0 to tempo-hold's tap trampoline (the tap with the
    # MIDI clock check), and CC 82 is the compare against 2 (80 + 2).
    step = PATCH["section"][1]
    raw = bytes.fromhex(step["data"])
    words = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]
    hold = patcher.load(ROOT / "patches/tempo-hold.yaml")
    tramp = next(e["addr"] for e in hold["write"] if e.get("source") == "asm/tempo_hold/tap_trampoline.S")
    assert f"TAP_TRAMPOLINE, 0x{tramp:X}" in (ROOT / "asm/midi_cc/step.S").read_text()
    const = lambda w: (w >> 7) & 0xFFFF
    mvk2 = [i for i, w in enumerate(words) if w == (2 << 7) | 0x28]          # mvk .S1 2,a0
    assert len(mvk2) == 1
    assert words[mvk2[0] + 1] == 0x01002A78                                  # cmpeq .L1 a1,a0,a2
    lo = [i for i, w in enumerate(words) if w & 0x7F == 0x2A and w >> 23 == 0 and const(w) == tramp & 0xFFFF]
    assert len(lo) == 1 and const(words[lo[0] + 1]) == tramp >> 16
    assert words[lo[0] + 2] == 0x00000362                                    # b .S2 b0
    # the CC 80/81 range check now branches to this code, not to stock
    assert ((words[4] >> 7) & 0x1FFFFF) == mvk2[0]
