import importlib.util
import struct
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/m0-probe.yaml")
CHAIN = patcher.load(ROOT / "patches/m0-probe-chain.yaml")  # the slot-loop hook, split off for mixer builds
CLOCK = patcher.load(ROOT / "patches/midi-clock.yaml")
SEC = PATCH["section"][0]
BASE = SEC["addr"]
WRITES = {w["addr"]: w for w in PATCH["write"] + CHAIN["write"]}

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
PROBE_SET = builder.PATCHES + ["m0-probe", "m0-probe-chain"]  # the probe build: release set, then these


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
    for w in PATCH["write"] + CHAIN["write"]:
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


def test_dsp_limit_225_to_300():
    old, new = (_word(bytes.fromhex(WRITES[0xC00BB52C][k])) for k in ("expect", "data"))
    field = 0xFFFF << 7                                             # mvkh cst16
    assert old & ~field == new & ~field                             # same mvkh .S2, b4
    high_half = lambda w: struct.unpack("<f", ((w >> 7 & 0xFFFF) << 16).to_bytes(4, "little"))[0]
    assert (high_half(old), high_half(new)) == (225.0, 300.0)      # the mvk 0 before it sets the low half


def test_stamp_fields_filled_at_build_time():
    from zoomms import cli
    texts = cli.build_stamp(["patches/version-1.2.yaml"], ["label=M0 PROBE V2"])
    assert texts["version"] == "V1.2" and texts["label"] == "M0 PROBE V2" and texts["commit"]
    assert len(texts["date"]) == 10 and texts["date"][4] == "-"                 # YYYY-MM-DD
    plain, filled = _data(SEC), patcher.stamp_section(SEC, texts)
    assert patcher.stamp_section(SEC, None) == plain                            # no text: placeholders stay
    for key, off in SEC["stamp"].items():
        assert plain[off:off + 16] == patcher.stamp_placeholder(key)
        assert filled[off:off + 16] == texts[key].encode()[:15].ljust(16, b"\0")
    changed = [i for i in range(len(plain)) if plain[i] != filled[i]]
    assert all(any(o <= i < o + 16 for o in SEC["stamp"].values()) for i in changed)
    with pytest.raises(patcher.PatchError):
        patcher.stamp_section({**SEC, "stamp": {"version": 0}}, texts)          # no placeholder there


def _disassemble():
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "a.ld").write_text(f"SECTIONS {{ . = 0x{BASE:08X}; .text : {{ *(.text) }} }}\n")
        run = lambda *a: subprocess.run(a, check=True, capture_output=True, text=True).stdout
        run(asm.PREFIX + "as", "-mlittle-endian", "-march=c674x", "-o", str(tmp / "a.o"), str(ROOT / SEC["source"]))
        run(asm.PREFIX + "ld", "-EL", "-T", str(tmp / "a.ld"), "-e", hex(BASE), "-o", str(tmp / "a.elf"), str(tmp / "a.o"))
        return run(asm.PREFIX + "objdump", "-d", str(tmp / "a.elf"))


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_audio_hooks_skip_everything_while_the_screen_is_closed():
    lines = _disassemble().splitlines()
    for entry, skip_to, most in (("blk_start", "bs_out", 7), ("blk_end", "be_out", 7), ("chain", "cf_slot", 8)):
        start = next(i for i, l in enumerate(lines) if l.endswith(f"<{entry}>:"))
        body = [l for l in lines[start + 1:] if l.count("\t") >= 2]
        first = next(i for i, l in enumerate(body) if " b .S" in l and l.split("\t")[2].startswith("[!"))
        assert first < most and f"<{skip_to}>" in body[first], (entry, body[first])   # a flag test, then out
        assert any("ldw" in l and "*-" in l for l in body[:first]), entry              # the flag below vars


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
    for w in PATCH["write"] + CHAIN["write"]:
        a, e = w["addr"], w["addr"] + len(bytes.fromhex(w["data"]))
        hits = [p for s, t, p in others if s < e and a < t]
        assert hits == ([] if a != 0xC00C6998 else ["midi-clock write"]), (hex(a), hits)
    # and the section stays clear of every release section and write
    assert not [p for s, t, p in others if s < BASE + len(_data(SEC)) and BASE < t]
