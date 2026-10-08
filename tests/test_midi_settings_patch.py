from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/midi-settings.yaml")
OTHERS = [patcher.load(ROOT / f"patches/{n}.yaml") for n in ("midi-cc", "midi-clock")]
BASE = 0x1181EA00


def _word(entry):
    return int.from_bytes(bytes.fromhex(entry["data"]), "little")


def _at(addr):
    return next(e for e in PATCH["write"] if e["addr"] == addr)


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_patch_bytes_match_assembly_source():
    for kind in ("write", "section"):
        for entry in PATCH[kind]:
            if "source" in entry:
                code = asm.assemble(ROOT / entry["source"], entry["addr"], whole_packets=kind == "section")
                assert code == bytes.fromhex(entry["data"]), entry["source"]


@pytest.mark.parametrize("site,tramp,vector", [
    (0xC00B9CF4, 0xC00B97E8, 24),  # pack
    (0xC00BA09C, 0xC00BDB44, 32),  # unpack
    (0xC00AF088, 0xC00B2FAC, 40),  # CC
    (0xC00AF0AC, 0xC00B2FAC, 40),  # PC
])
def test_call_sites_reach_their_vector(site, tramp, vector):
    word = _word(_at(site))
    disp = (word >> 7) & 0x1FFFFF
    disp = disp - (1 << 21) if disp & (1 << 20) else disp
    assert (site & ~31) + 4 * disp == tramp
    assert word & 0x7E == 0x12 and word >> 28 == 1  # callp .S2
    t = bytes.fromhex(_at(tramp)["data"])
    assert len(t) <= 16
    lo = (int.from_bytes(t[0:4], "little") >> 7) & 0xFFFF
    hi = (int.from_bytes(t[4:8], "little") >> 7) & 0xFFFF
    assert (hi << 16 | lo) == BASE + vector


def test_switch_tables_and_tables():
    assert _word(_at(0xC00EF300)) == BASE + 0   # screen 1 keys
    assert _word(_at(0xC00EF330)) == BASE + 8   # screen 13 keys
    assert _word(_at(0xC00EF2EC)) == BASE + 16  # screen 13 draw
    sec = bytes.fromhex(PATCH["section"][0]["data"])
    names = [int.from_bytes(sec[64 + 4 * i:68 + 4 * i], "little") for i in range(12)]
    assert names[:7] == [0xC00E94B5, 0xC00E94C8, 0xC00E94DA, 0xC00E94EB, 0xC00E94F5, 0xC00E9502, 0xC00E9510]
    assert names[11] == 0
    strings = [sec[a - BASE:].split(b"\0")[0] for a in names[7:11]]
    assert strings == [b"MIDI CLOCK", b"MIDI START/STOP", b"MIDI PROG CHANGE", b"MIDI CC"]
    assert sec[48:56] == bytes(8)  # flags and item start at 0 = all on
    assert "MIDI_FLAGS, 0x1181EA30" in (ROOT / "asm/midi_clock/transport.inc").read_text()


def test_no_overlap():
    def spans(p):
        for e in p.get("write", []) + p.get("section", []):
            yield e["addr"], e["addr"] + len(bytes.fromhex(e["data"]))
    ours = list(spans(PATCH))
    for o in OTHERS:
        for a, b in spans(o):
            for c, d in ours:
                if a == c == 0xC00AF088:  # the CC call site, rerouted on purpose
                    continue
                assert b <= c or d <= a, hex(c)
    end = PATCH["section"][0]["addr"] + len(bytes.fromhex(PATCH["section"][0]["data"]))
    assert end <= 0x1181FF00  # transport block
