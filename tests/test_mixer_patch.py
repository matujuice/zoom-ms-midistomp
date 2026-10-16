import importlib.util
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/mixer-m1.yaml")
PROBE_CHAIN = patcher.load(ROOT / "patches/m0-probe-chain.yaml")
SEC = PATCH["section"][0]
BASE = SEC["addr"]
JUMP = PATCH["write"][0]

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
M1_SET = builder.PATCHES + ["m0-probe", "mixer-m1"]  # the M1 test build: release set, probe P1, engine


def _data(entry):
    return bytes.fromhex("".join(entry["data"].split()))


def _word(data, i=0):
    return int.from_bytes(data[4 * i:4 * i + 4], "little")


def far_target(hexdata):
    """mvkl/mvkh .S2 target, b31: the 16-bit constants sit in bits 7-22."""
    lo, hi = (_word(bytes.fromhex(hexdata), i) >> 7 & 0xFFFF for i in (0, 1))
    return hi << 16 | lo


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    assert asm.assemble(ROOT / SEC["source"], BASE, whole_packets=True) == _data(SEC)
    code, data = asm.assemble(ROOT / JUMP["source"], JUMP["addr"]), _data(JUMP)
    assert data == code + b"\0" * (len(data) - len(code))  # zero words = nops


def test_slot_loop_jumps_to_the_engine():
    assert JUMP["addr"] == 0x1181BE00
    assert JUMP["expect"] == PROBE_CHAIN["write"][0]["expect"]     # the stock packet, as the probe hooks it
    assert far_target(JUMP["data"]) == BASE
    data = _data(JUMP)
    assert len(data) == 32 and data[16:] == b"\0" * 16              # a whole plain packet: no stale header
    assert all(_word(data, i) & 1 == 0 for i in range(8))           # serial: nothing runs with the branch


def test_vector_and_layout():
    data = _data(SEC)
    w = _word(data)
    assert w & 0x7F == 0x12 and _word(data, 1) == 0x8000            # b .S2 engine ; nop 5
    assert BASE + 64 == BASE + 4 * (w >> 7 & 0x1FFFFF)              # engine right after the layout packet
    assert data[8:32] == b"\0" * 24                                 # rest of the vector packet: nops
    assert list(data[32:38]) == [0, 0, 1, 2, 3, 3]                  # PRE PRE A B POST POST, slot 0 first
    assert data[38:64] == b"\0" * 26
    assert len(data) % 32 == 0


def test_engine_and_probe_chain_exclude_each_other():
    assert JUMP["addr"] == PROBE_CHAIN["write"][0]["addr"]         # same packet: one build has one of them


def _spans(names):
    for p in names:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        for s in patch.get("section", []):
            yield s["addr"], s["addr"] + len(_data(s)), p
        for w in patch.get("write", []):
            yield w["addr"], w["addr"] + len(bytes.fromhex(w["data"])), p + " write"


def test_m1_build_does_not_overlap():
    sections = sorted(s for s in _spans(M1_SET) if not s[2].endswith("write"))
    for (_, end, a), (start, _, b) in zip(sections, sections[1:]):
        assert end <= start, f"{a} and {b} overlap at 0x{start:08X}"
    others = [s for s in _spans(M1_SET) if not s[2].startswith("mixer-m1")]
    for a, e, _ in _spans(["mixer-m1"]):                            # the engine touches nothing else's bytes
        assert not [p for s, t, p in others if s < e and a < t], hex(a)
    assert BASE + len(_data(SEC)) <= 0xC0102000                     # inside the 64 KB MOD code area (looper buffer above)
