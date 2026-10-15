import importlib.util
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/m0-probe.yaml")
CLOCK = patcher.load(ROOT / "patches/midi-clock.yaml")
SEC = PATCH["section"][0]
BASE = SEC["addr"]
WRITES = {w["addr"]: w for w in PATCH["write"]}

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
PROBE_SET = builder.PATCHES + ["m0-probe"]  # the probe build: release set, then this patch


def _data(entry):
    return bytes.fromhex("".join(entry["data"].split()))


def _word(data, i=0):
    return int.from_bytes(data[4 * i:4 * i + 4], "little")


def callp_target(addr, hexdata):
    disp = _word(bytes.fromhex(hexdata)) >> 7 & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp >> 20 else disp)


def far_target(hexdata):
    """mvkl/mvkh .S2 target, b31: the 16-bit constants sit in bits 7-22."""
    lo, hi = (_word(bytes.fromhex(hexdata), i) >> 7 & 0xFFFF for i in (0, 1))
    return hi << 16 | lo


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    assert asm.assemble(ROOT / SEC["source"], BASE, whole_packets=True) == _data(SEC)
    for w in PATCH["write"]:
        if "source" in w:
            code, data = asm.assemble(ROOT / w["source"], w["addr"]), _data(w)
            assert data == code + b"\0" * (len(data) - len(code))  # zero words = nops


def test_audio_hooks():
    # the block's register save / restore stubs keep their b b31, now to the vectors
    assert far_target(WRITES[0x1181BF60]["expect"]) == 0xC00E14C0
    assert far_target(WRITES[0x1181BF60]["data"]) == BASE + 0      # blk_start
    assert far_target(WRITES[0x1181BF40]["expect"]) == 0xC00E14A0
    assert far_target(WRITES[0x1181BF40]["data"]) == BASE + 8      # blk_end
    jump = WRITES[0x1181BE00]
    assert far_target(jump["data"]) == BASE + 16                   # chain
    data = _data(jump)
    assert len(data) == 32 and data[16:] == b"\0" * 16              # a whole plain packet: no stale header
    assert all(_word(data, i) & 1 == 0 for i in range(8))           # serial: nothing runs with the branch


def test_ui_call_sites():
    clock = next(e for e in CLOCK["write"] if e["addr"] == 0xC00C6998)
    assert WRITES[0xC00C6998]["expect"] == clock["data"]           # on top of midi-clock.yaml
    assert callp_target(0xC00C6998, WRITES[0xC00C6998]["data"]) == BASE + 24   # probe_poll
    assert callp_target(0xC00A93D0, WRITES[0xC00A93D0]["expect"]) == 0xC00A8428  # stock version draw
    assert callp_target(0xC00A93D0, WRITES[0xC00A93D0]["data"]) == BASE + 32   # probe_draw
    assert callp_target(0xC00A8364, WRITES[0xC00A8364]["expect"]) == 0xC00A7628  # stock version keys
    assert callp_target(0xC00A8364, WRITES[0xC00A8364]["data"]) == BASE + 40   # probe_keys
    for addr in (0xC00C6998, 0xC00A93D0, 0xC00A8364):
        old, new = (_word(bytes.fromhex(WRITES[addr][k])) for k in ("expect", "data"))
        assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)     # still callp .S2 b3, parallel bit kept


def test_vectors_branch_into_the_section():
    data = _data(SEC)
    for i in range(6):
        w = _word(data, 2 * i)
        assert w & 0x7F == 0x12 and _word(data, 2 * i + 1) == 0x8000   # b .S2 disp ; nop 5
        disp = w >> 7 & 0x1FFFFF
        target = BASE + 8 * i - (BASE + 8 * i) % 32 + 4 * disp
        assert BASE + 48 <= target < BASE + len(data)


def _spans(names):
    for p in names:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        for s in patch.get("section", []):
            yield s["addr"], s["addr"] + len(_data(s)), p
        for w in patch.get("write", []):
            yield w["addr"], w["addr"] + len(bytes.fromhex(w["data"])), p + " write"


def test_probe_build_does_not_overlap():
    sections = sorted((a, e, p) for a, e, p in _spans(PROBE_SET) if not p.endswith("write"))
    for (_, end, a), (start, _, b) in zip(sections, sections[1:]):
        assert end <= start, f"{a} and {b} overlap at 0x{start:08X}"
    # the probe's writes only touch what no other patch in the set writes, except the
    # poll call it takes over from midi-clock.yaml (checked by its expect)
    others = [(a, e, p) for a, e, p in _spans(builder.PATCHES)]
    for w in PATCH["write"]:
        a, e = w["addr"], w["addr"] + len(bytes.fromhex(w["data"]))
        hits = [p for s, t, p in others if s < e and a < t]
        assert hits == ([] if a != 0xC00C6998 else ["midi-clock write"]), (hex(a), hits)
    # and the section stays clear of every release section and write
    assert not [p for s, t, p in others if s < BASE + len(_data(SEC)) and BASE < t]
