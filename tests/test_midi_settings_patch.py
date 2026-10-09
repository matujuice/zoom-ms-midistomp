from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/midi-settings.yaml")
OTHERS = [patcher.load(ROOT / f"patches/{n}.yaml") for n in ("midi-cc", "midi-clock")]
BASE = 0x1181EA00
SEC = bytes.fromhex(PATCH["section"][0]["data"])


def _word(entry):
    return int.from_bytes(bytes.fromhex(entry["data"]), "little")


def _at(addr):
    return next(e for e in PATCH["write"] if e["addr"] == addr)


def _sec_word(addr):
    return int.from_bytes(SEC[addr - BASE:addr - BASE + 4], "little")


def _sec_str(addr):
    return SEC[addr - BASE:].split(b"\0")[0].decode()


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_patch_bytes_match_assembly_source():
    for kind in ("write", "section"):
        for entry in PATCH[kind]:
            if "source" in entry:
                code = asm.assemble(ROOT / entry["source"], entry["addr"], whole_packets=kind == "section")
                assert code == bytes.fromhex(entry["data"]), entry["source"]


@pytest.mark.parametrize("site,tramp,vector", [
    (0xC00A8360, 0xC00BEDF0, 64),   # menu keys
    (0xC00A9400, 0xC00C2164, 72),   # menu draw
    (0xC00B9CF4, 0xC00B97E8, 128),  # settings pack
    (0xC00BA09C, 0xC00BDB44, 136),  # settings unpack
    (0xC00AF088, 0xC00B2FAC, 144),  # CC
    (0xC00AF0AC, 0xC00B2FAC, 144),  # PC
    (0xC00B8DD4, 0xC00C4AAC, 152),  # record 51 load
    (0xC00B86E0, 0xC00C5D88, 160),  # record 51 save
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


def test_switch_tables():
    assert _word(_at(0xC00EF300)) == BASE + 80   # screen 1 keys
    assert _word(_at(0xC00EF2BC)) == BASE + 88   # screen 1 draw
    assert _word(_at(0xC00EF334)) == BASE + 96   # screen 14 keys
    assert _word(_at(0xC00EF2F0)) == BASE + 104  # screen 14 draw
    assert _word(_at(0xC00EF330)) == BASE + 112  # screen 13 keys
    assert _word(_at(0xC00EF2EC)) == BASE + 120  # screen 13 draw


def test_vars_and_shared_addresses():
    assert SEC[0:32] == bytes(32)  # MIDI word etc. start at 0 = defaults
    assert _sec_word(BASE + 32) == 125  # V_BOOT
    assert "MIDI_FLAGS, 0x1181EA00" in (ROOT / "asm/midi_clock/transport.inc").read_text()
    assert "TEMPO_LOCK, 0x1181EAA8" in (ROOT / "asm/midi_clock/poll.S").read_text()


def test_settings_table():
    items = SEC.index((0x1181EA00 + 12).to_bytes(4, "little")) - 4  # TEMPO LOCK's word
    first = items - 6 * 24
    rows = []
    for i in range(8):
        d = SEC[first + 24 * i:first + 24 * i + 24]
        name, word, choices = (int.from_bytes(d[k:k + 4], "little") for k in (0, 4, 8))
        rows.append((_sec_str(name), word, tuple(d[12:18])))
    assert rows == [
        ("CLOCK RECEIVE", 0x1181EA00, (0, 1, 1, 2, 14, 0)),
        ("TRANSPORT RECEIVE", 0x1181EA00, (1, 1, 1, 2, 14, 1)),
        ("PROG CH RECEIVE", 0x1181EA00, (2, 1, 1, 2, 14, 2)),
        ("PROG CH START NO.", 0x1181EA00, (4, 1, 1, 2, 14, 3)),
        ("CC RECEIVE", 0x1181EA00, (3, 1, 1, 2, 14, 4)),
        ("MIDI CHANNEL", 0x1181EA00, (5, 31, 0, 17, 14, 5)),
        ("TEMPO LOCK", 0x1181EA0C, (0, 1, 0, 2, 1, 7)),
        ("HOLD FOR", 0xC009D920, (0, 0, 0, 3, 1, 0)),
    ]
    hold = int.from_bytes(SEC[first + 7 * 24 + 8:first + 7 * 24 + 12], "little")
    assert [_sec_word(hold + 4 * k) for k in range(2)] == [0xC00E953F, 0xC00EB13F]  # stock TUNER, TEMPO
    assert _sec_str(_sec_word(hold + 8)) == "MOMENTARY"


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
    for i, (a, b) in enumerate(ours):
        for c, d in ours[i + 1:]:
            assert b <= c or d <= a, hex(c)
    end = PATCH["section"][0]["addr"] + len(SEC)
    assert end <= 0x1181FF00  # transport block
