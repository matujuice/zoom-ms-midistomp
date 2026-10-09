import re
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/tempo-hold.yaml")
OTHERS = [patcher.load(ROOT / f"patches/{n}.yaml") for n in ("midi-cc", "midi-clock", "midi-settings")]
H, H2 = 0x1181FA80, 0x1181FF20


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
    (0xC00BA930, 0xC00CBA70, H + 0),    # tempo screen draw
    (0xC00AD10C, 0xC00D1BB0, H + 8),    # knob turn
    (0xC00AC9F0, 0xC00D2030, H + 16),   # knob press tap
    (0xC00ACA50, 0xC00D2030, H + 16),   # footswitch tap
    (0xC00ACC2C, 0xC00D3370, H + 24),   # footswitch flip
    (0xC00AD2D8, 0xC00D3F30, H + 32),   # footswitch release
    (0xC00AD090, 0xC00D44D0, H + 40),   # type hold 228
    (0xC00AD064, 0xC00D44D0, H + 40),   # type hold 229
    (0xC00AD034, 0xC00D44D0, H + 40),   # cursor hold 230/231
    (0xC00AD0E4, 0xC00D46B0, H2 + 0),   # footswitch hold
    (0xC00ACCE4, 0xC00D4BF0, H2 + 8),   # AUTO SAVE check
    (0xC00AD1F8, 0xC00D8B70, H2 + 16),  # type release 69
    (0xC00AD1A8, 0xC00D8B70, H2 + 16),  # type release 71
    (0xC00AD158, 0xC00D8B70, H2 + 16),  # cursor release 73/75
])
def test_call_sites_reach_their_vector(site, tramp, vector):
    entry = _at(site)
    old, word = int.from_bytes(bytes.fromhex(entry["expect"]), "little"), _word(entry)
    assert word & 0xF000007F == old & 0xF000007F  # only the displacement changes
    disp = (word >> 7) & 0x1FFFFF
    disp = disp - (1 << 21) if disp & (1 << 20) else disp
    assert (site & ~31) + 4 * disp == tramp
    assert word & 0x7E == 0x12 and word >> 28 == 1  # callp .S2
    t = bytes.fromhex(_at(tramp)["data"])
    assert len(t) <= 16
    lo = (int.from_bytes(t[0:4], "little") >> 7) & 0xFFFF
    hi = (int.from_bytes(t[4:8], "little") >> 7) & 0xFFFF
    assert (hi << 16 | lo) == vector


def test_word_patches():
    def cst(addr):  # mvk: register, 16-bit constant, p-bit
        w = _word(_at(addr))
        assert w & 0x7C == 0x28
        return (w >> 23) & 31, (w >> 7) & 0xFFFF, w & 1
    assert cst(0xC00ACBD8) == (4, 1, 0)       # a4 = 1: "HOLD FOR is TEMPO"
    assert cst(0xC00ACA40) == (4, 1, 0)
    assert cst(0xC00CB96C) == (6, 2000, 1)    # tempo screen closes after 2 s
    assert cst(0xC00CB3C8) == (4, 0xB13F, 0)  # mvkh 0xC00E: "TEMPO"


def test_tempo_box_reaches_bottom_row():
    box = bytes.fromhex(_at(0xC00EBB64)["data"])
    x, y, w, h = (int.from_bytes(box[k:k + 2], "little") for k in range(0, 8, 2))
    assert (x, w) == (4, 120) and y + h - 1 == 63
    assert "TEXT_Y, 53" in (ROOT / "asm/tempo_hold/hold.inc").read_text()  # 7-px font: rows 53-59


def test_shared_addresses():
    inc = (ROOT / "asm/tempo_hold/hold.inc").read_text()
    settings = (ROOT / "asm/midi_settings/settings.S").read_text()
    assert "HV, 0x1181EA24" in inc and "V_HOLDM, 36" in settings  # settings base + 36
    assert "HOLD_WORD, 0xC009D920" in inc and "HOLD_WORD, 0xC009D920" in settings
    # hold.S's variables are settings.S's trailing zero words
    assert re.search(r"V_HOLDM\n\s+\.word\s+0, 0, 0, 0, 0, 0 +; \+40\.\. hold\.S", settings)


def test_strings():
    sec = bytes.fromhex(PATCH["section"][0]["data"])
    assert b"TURN OR TAP\0" in sec and b"MIDI CLOCK\0" in sec


def test_sections_fit_free_l2():
    a, b = PATCH["section"]
    assert a["addr"] == H and H + len(bytes.fromhex(a["data"])) <= 0x1181FF00  # transport block
    assert b["addr"] == H2 and H2 + len(bytes.fromhex(b["data"])) <= 0x11820000  # end of L2
    settings = next(o for o in OTHERS if o["name"] == "midi-settings")["section"][0]
    assert settings["addr"] + len(bytes.fromhex(settings["data"])) <= H


def test_no_overlap():
    def spans(p):
        for e in p.get("write", []) + p.get("section", []):
            yield e["addr"], e["addr"] + len(bytes.fromhex(e["data"]))
    ours = list(spans(PATCH))
    theirs = [s for o in OTHERS for s in spans(o)]
    for i, (a, b) in enumerate(ours):
        for c, d in ours[i + 1:] + theirs:
            assert b <= c or d <= a, hex(a)
