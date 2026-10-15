"""MIDISTOMP on the MS-70CDR 2.10 OS (build id ms70cdr-2.10), phase 1:
version-1.1, boot-logo, midi-cc, midi-clock. Addresses: docs/ms70cdr-port.md,
"Port to the MS-70CDR OS". Byte-vs-source checks are in test_midi_c*_patch.py."""

import re
from pathlib import Path

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
    for name in ("version-1.1", "midi-cc", "midi-clock"):
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
