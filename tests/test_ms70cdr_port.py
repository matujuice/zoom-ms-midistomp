"""MIDISTOMP on the MS-70CDR 2.10 OS (build id ms70cdr-2.10): phase 1
version-1.1, boot-logo, midi-cc, midi-clock; phase 2 midi-settings,
tempo-hold, scroll; phase 3 looper. Addresses: docs/ms70cdr-port.md, "Port to the MS-70CDR
OS". Byte-vs-source checks are in the test_<patch>_patch.py files."""

import re
from pathlib import Path

import pytest

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
B = "ms70cdr-2.10"
OS_L2_END = 0x1181DF04  # .cinit L2 data 0x1181DD60 + 420 B; highest mvkl/mvkh L2 address 0x1181DF00


def entries(name, kind):
    return [e for e in patcher.load(ROOT / f"patches/{name}.yaml").get(kind, []) if e["model"] == B]


def os_inc(build):
    text = (ROOT / f"asm/os/{build}/os.inc").read_text()
    return {m[1]: int(m[2], 0) for m in re.finditer(r"\.equ\s+(\w+),\s*(\w+)", text)}


def word(hexdata, i=0):
    return int.from_bytes(bytes.fromhex(hexdata)[4 * i:4 * i + 4], "little")


def far_target(hexdata):
    """mvkl/mvkh .S2 target, b0: the 16-bit constants sit in bits 7-22."""
    return (word(hexdata, 1) >> 7 & 0xFFFF) << 16 | word(hexdata, 0) >> 7 & 0xFFFF


def callp_target(addr, w):
    disp = w >> 7 & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp >> 20 else disp)


def test_os_files_define_the_same_names():
    assert os_inc("ms50g-3.10").keys() == os_inc(B).keys()


def test_new_sections_avoid_the_os():
    for name in ("version-1.1", "midi-cc", "midi-clock", "midi-settings", "tempo-hold", "scroll"):
        for s in entries(name, "section"):
            end = s["addr"] + len(bytes.fromhex("".join(s["data"].split())))
            assert OS_L2_END <= s["addr"] and end <= 0x11820000 or 0xC00F2000 <= s["addr"] and end <= 0xC00F3000


def test_cc_path():
    site, tramp = entries("midi-cc", "write")
    handler, step = entries("midi-cc", "section")
    assert callp_target(site["addr"], word(site["expect"])) == os_inc(B)["MIDI_CHANNEL_MSG"]
    assert callp_target(site["addr"], word(site["data"])) == tramp["addr"]
    assert word(site["data"]) & ~(0x1FFFFF << 7) == word(site["expect"]) & ~(0x1FFFFF << 7)
    assert far_target(tramp["data"]) == os_inc(B)["CC_HANDLER"] == handler["addr"] == 0xC00F2800
    assert step["addr"] == 0xC00F2020  # handler.S STEP, the same on both builds


def test_clock_and_poll_hooks():
    hook, tramp, poll, ptramp = entries("midi-clock", "write")
    clock, _, poll_sec, block = entries("midi-clock", "section")
    assert hook["expect"] == "6e360000"  # ldw *+b14(216),b0: MIDI_RD_OFS
    assert os_inc(B)["MIDI_RD_OFS"] == 216
    new = word(hook["data"])
    assert new & 0x7F == 0x12 and new >> 28 == 1  # callp .S2, p-bit clear like the ldw
    assert callp_target(hook["addr"], new) == tramp["addr"] and far_target(tramp["data"]) == clock["addr"]
    assert callp_target(poll["addr"], word(poll["expect"])) == os_inc(B)["CLOCK_GETTICKS"]
    assert callp_target(poll["addr"], word(poll["data"])) == ptramp["addr"]
    assert far_target(ptramp["data"]) == poll_sec["addr"]
    assert block["addr"] == 0x1181FF00 and word(block["data"]) == 0x5A4D5401


def test_version_string_pointer():
    (w,), (s,) = entries("version-1.1", "write"), entries("version-1.1", "section")
    lo, hi = word(w["data"], 0) >> 7 & 0xFFFF, word(w["data"], 1) >> 7 & 0xFFFF
    assert hi << 16 | lo == s["addr"] and bytes.fromhex(s["data"]).startswith(b"v1.1\0")


def test_boot_logo_only_replaces_the_70cdr_picture():
    (b,) = entries("boot-logo", "bin133")
    g50 = patcher.load(ROOT / "patches/boot-logo.yaml")["bin133"][0]
    assert b["data"] == g50["data"] and b["expect_sha256"] != g50["expect_sha256"]
    assert b["offset"] == 0 and len(bytes.fromhex(b["data"])) == 1024  # the model byte at 0x2C00 stays


# Phase 2 ------------------------------------------------------------------

PHASE1_CAVES = {0xC00E1F70, 0xC00A1A50, 0xC00C82D0}
SB, H, H2 = 0x1181EA00, 0x1181FA80, 0x1181FF20  # settings.S, hold.S, hold2.S: 50G addresses kept


def at(name, addr):
    (e,) = [e for e in entries(name, "write") if e["addr"] == addr]
    return e


@pytest.mark.parametrize("name, site, stock, tramp, vector", [
    ("midi-settings", 0xC00A8310, "STOCK_MENU_KEYS", 0xC00BB190, SB + 64),
    ("midi-settings", 0xC00A9398, 0xC00A7460, 0xC00BEC90, SB + 72),  # stock menu draw
    ("midi-settings", 0xC00BA3D4, "PACK", 0xC00C3530, SB + 128),
    ("midi-settings", 0xC00BA77C, "UNPACK", 0xC00D1770, SB + 136),
    ("midi-settings", 0xC00AEE6C, 0xC00E1F70, 0xC00D3AF0, SB + 144),  # CC: midi-cc's trampoline
    ("midi-settings", 0xC00AEE90, "MIDI_CHANNEL_MSG", 0xC00D3AF0, SB + 144),  # PC
    ("midi-settings", 0xC00B8B14, "REC_LOAD", 0xC00D1BF0, SB + 152),
    ("midi-settings", 0xC00B8420, "REC_SAVE", 0xC00D2F30, SB + 160),
    ("tempo-hold", 0xC00BB050, "TEMPO_BOX", 0xC00D4090, H + 0),
    ("tempo-hold", 0xC00ACFE8, "STOCK_KNOB", 0xC00D4270, H + 8),
    ("tempo-hold", 0xC00AC8D0, "STOCK_TAP", 0xC00D47B0, H + 16),
    ("tempo-hold", 0xC00AC930, "STOCK_TAP", 0xC00D47B0, H + 16),
    ("tempo-hold", 0xC00ACB0C, "TOGGLE", 0xC00D86F0, H + 24),
    ("tempo-hold", 0xC00AD1B8, "STOCK_RELEASE", 0xC00D8D10, H + 32),
    ("tempo-hold", 0xC00ACF6C, "STOCK_TYPE_HOLD", 0xC00DAA30, H + 40),
    ("tempo-hold", 0xC00ACF40, "STOCK_TYPE_HOLD", 0xC00DAA30, H + 40),
    ("tempo-hold", 0xC00ACF10, "STOCK_CURSOR_HOLD", 0xC00DAA30, H + 40),
    ("tempo-hold", 0xC00ACFC0, "STOCK_HOLD", 0xC00DB590, H2 + 0),
    ("tempo-hold", 0xC00ACBC4, "IS_DIRTY", 0xC00DBF30, H2 + 8),
    ("tempo-hold", 0xC00AD0D8, "STOCK_TYPE_REL", 0xC00DFDB0, H2 + 16),
    ("tempo-hold", 0xC00AD088, "STOCK_TYPE_REL", 0xC00DFDB0, H2 + 16),
    ("tempo-hold", 0xC00AD038, "STOCK_CURSOR_REL", 0xC00DFDB0, H2 + 16),
    ("tempo-hold", 0xC00AD170, "STOCK_MIDDLE", 0xC00DF750, 0x1181E7C0),
])
def test_call_sites_reach_their_vectors(name, site, stock, tramp, vector):
    e, t = at(name, site), at(name, tramp)
    old, new = word(e["expect"]), word(e["data"])
    assert callp_target(site, old) == (os_inc(B)[stock] if isinstance(stock, str) else stock)
    assert callp_target(site, new) == tramp
    assert new & ~(0x1FFFFF << 7) == old & ~(0x1FFFFF << 7)  # only the displacement changes
    assert t["expect"] == "00" * 16 and tramp not in PHASE1_CAVES
    assert far_target(t["data"]) == vector


def test_caves_are_distinct():
    caves = [e["addr"] for n in ("midi-settings", "tempo-hold") for e in entries(n, "write")
             if e.get("expect") == "00" * 16]
    assert len(caves) == len(set(caves)) == 18 and not set(caves) & PHASE1_CAVES
    assert os_inc(B)["TUNER_LABEL_TRAMP"] in caves


def test_switch_tables():
    # keys at 0xC00EEF9C + 4 x screen, draws at 0xC00EEBB0 + 4 x screen; 13 and 14 are the default stubs
    for addr, stub, vector in ((0xC00EEFA0, None, 80), (0xC00EEBB4, None, 88), (0xC00EEFD4, 0xC00A8310, 96),
                               (0xC00EEBE8, 0xC00A9398, 104), (0xC00EEFD0, 0xC00A8310, 112), (0xC00EEBE4, 0xC00A9398, 120)):
        e = at("midi-settings", addr)
        assert word(e["data"]) == SB + vector
        assert stub is None or word(e["expect"]) == stub


def test_tempo_hold_word_patches():
    def cst(addr):
        w = word(at("tempo-hold", addr)["data"])
        assert w & 0x7C == 0x28  # mvk
        return (w >> 23) & 31, (w >> 7) & 0xFFFF, w & 1
    assert cst(0xC00ACAB8) == cst(0xC00AC920) == (4, 1, 0)  # a4 = 1: "HOLD FOR is TEMPO"
    assert cst(0xC00CCCC8) == (6, 2000, 1)  # state 2 closes after 2 s
    assert cst(0xC00CB2A8) == (4, os_inc(B)["STR_TEMPO"] & 0xFFFF, 0)  # mvkh 0xC00E: "TEMPO"
    assert at("tempo-hold", 0xC00EB700)["data"] == "04001b0078002500"  # same box as the 50G


def test_tuner_label_trampoline():
    site, t = at("tempo-hold", 0xC00BAD40), os_inc(B)["TUNER_LABEL_TRAMP"]
    assert callp_target(0xC00BAD40, word(site["expect"])) == os_inc(B)["SOFTKEY"]
    assert callp_target(0xC00BAD40, word(site["data"])) == t
    data = at("tempo-hold", t)["data"]
    assert far_target(data) == os_inc(B)["STR_EXIT"]
    assert callp_target(t, word(data, 2)) == os_inc(B)["SOFTKEY"]  # b .S2: same displacement field


def test_scroll_sites():
    sleep, right, left, bump_sleep = entries("scroll", "write")
    (sec,) = entries("scroll", "section")
    for s in (sleep, bump_sleep):
        assert callp_target(s["addr"], word(s["expect"])) == os_inc(B)["STOCK_SLEEP"]
        assert callp_target(s["addr"], word(s["data"])) == sec["addr"] == 0xC00F2100
    for s in (right, left):
        assert callp_target(s["addr"], word(s["expect"])) == os_inc(B)["STOCK_BUMP"]
        assert callp_target(s["addr"], word(s["data"])) == sec["addr"] + 0x1C  # wrap


def test_phase2_l2_and_ddr_layout():
    """The 50G L2 addresses, no overlap with each other or with phase 1."""
    spans = []
    for n in ("version-1.1", "midi-cc", "midi-clock", "midi-settings", "tempo-hold", "scroll"):
        for kind in ("write", "section"):
            for e in entries(n, kind):
                if n == "midi-cc" and e["addr"] == 0xC00AEE6C:
                    continue  # the CC call site, rerouted by midi-settings on purpose
                spans.append((e["addr"], e["addr"] + len(bytes.fromhex("".join(e["data"].split()))), n))
    spans.sort()
    for (_, end, a), (start, _, b) in zip(spans, spans[1:]):
        assert end <= start, f"{a} and {b} overlap at 0x{start:08X}"
    secs = {e["addr"] for n in ("midi-settings", "tempo-hold") for e in entries(n, "section")}
    assert secs == {SB, H, H2, 0x1181E7C0}


# Phase 3 ------------------------------------------------------------------

LOOPER_HOOKS, SERVICES = 0xC00F2200, 0xC00F3000  # the 50G DDR addresses, kept


def test_looper_trampolines_retarget_the_phase_1_2_ones():
    poll, toggle, hold, cc, draw = entries("looper", "write")
    for i, (e, owner) in enumerate(((poll, "midi-clock"), (toggle, "tempo-hold"), (hold, "tempo-hold"), (cc, "midi-cc"))):
        assert e["expect"] == at(owner, e["addr"])["data"]  # what the earlier patch put there
        assert far_target(e["data"]) == LOOPER_HOOKS + 8 * i
    assert far_target(poll["expect"]) == 0x1181E800 and far_target(toggle["expect"]) == H + 24
    assert far_target(hold["expect"]) == H2 and far_target(cc["expect"]) == os_inc(B)["CC_HANDLER"]
    # midi_gate passes CCs on through that trampoline, so cc_pre is on the CC path
    assert os_inc(B)["CC_TRAMP"] == cc["addr"] == 0xC00E1F70


def test_looper_draw_site():
    *_, draw = entries("looper", "write")
    old, new = word(draw["expect"]), word(draw["data"])
    assert draw["addr"] == 0xC00BB0EC
    assert callp_target(draw["addr"], old) == os_inc(B)["DRAW_NEXT"] == 0xC00D5720
    assert callp_target(draw["addr"], new) == LOOPER_HOOKS + 32  # draw_pre
    assert new & ~(0x1FFFFF << 7) == old & ~(0x1FFFFF << 7)  # callp .S2, parallel bit kept


def test_looper_sections():
    hooks, block = entries("looper", "section")
    g50 = [e for e in patcher.load(ROOT / "patches/looper.yaml")["section"] if e["model"] == "ms50g-3.10"]
    size = len(bytes.fromhex("".join(hooks["data"].split())))
    assert hooks["addr"] == LOOPER_HOOKS and hooks["addr"] + size == os_inc(B)["CC_HANDLER"]  # ends where the handler starts
    assert block["addr"] == SERVICES and block["data"] == g50[1]["data"]  # the Looper ZDL's layout, unchanged
    spans = sorted((e["addr"], e["addr"] + len(bytes.fromhex("".join(e["data"].split()))))
                   for n in ("version-1.1", "midi-cc", "midi-clock", "scroll", "looper") for e in entries(n, "section")
                   if e["addr"] >> 24 == 0xC0)
    for (_, end), (start, _) in zip(spans, spans[1:]):
        assert end <= start
    assert spans[-1][1] <= 0xC0102000  # the 64 KB kept for MOD code, below big-buffer region 1


def test_looper_os_addresses():
    o, g = os_inc(B), os_inc("ms50g-3.10")
    same = ("SLOT_STATE", "SLOT_STRIDE", "CURSOR", "FB", "VIEW_KNOBS", "EV_REDRAW")
    assert all(o[k] == g[k] for k in same)  # the same in both OS images (docs/ms70cdr-port.md)
    assert (o["GPIO_BANK01"], o["LED_APPLIED"], o["CURSOR_SLOT"]) == (0x1181DEF0, 0xC00EEB10, 0xC00EE748)
    assert (o["FB_DIRTY"], o["FONT7"], o["UI_EVENT_OFS"]) == (0xC00EEB30, 0xC00E87D8, 656)
    assert o["GPIO_BANK01"] < OS_L2_END  # OS data, initialised from .cinit
