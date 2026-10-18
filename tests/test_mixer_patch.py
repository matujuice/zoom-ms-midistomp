import importlib.util
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/mixer-m2.yaml")
PROBE_CHAIN = patcher.load(ROOT / "patches/m0-probe-chain.yaml")
SETTINGS = patcher.load(ROOT / "patches/midi-settings.yaml")
MIDI_CC = patcher.load(ROOT / "patches/midi-cc.yaml")
SEC = PATCH["section"][0]
BASE = SEC["addr"]
WRITES = {w["addr"]: w for w in PATCH["write"]}
JUMP = WRITES[0x1181BE00]

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
M2_SET = builder.PATCHES + ["m0-probe", "mixer-m2"]  # the M2 test build: release set, probe P1, mixer

# mixer.S fixed offsets
VEC = {"engine": 0, "unpack_live": 8, "unpack_saved": 16, "pack_dump": 24, "dirty": 32,
       "rec_save": 40, "keys": 48, "draw": 56, "cc": 64, "poll": 120}
LAYOUT, MAIL, LIVE, SAVED, MENU6, MAXES, DEFAULTS, PAGES = 128, 136, 144, 156, 200, 224, 236, 248
MAGIC = 0x4D


def _data(entry):
    return bytes.fromhex("".join(entry["data"].split()))


def _word(data, i=0):
    return int.from_bytes(data[4 * i:4 * i + 4], "little")


def far_target(hexdata):
    """mvkl/mvkh target, reg: the 16-bit constants sit in bits 7-22."""
    lo, hi = (_word(bytes.fromhex(hexdata), i) >> 7 & 0xFFFF for i in (0, 1))
    return hi << 16 | lo


def callp_target(site, word):
    disp = word >> 7 & 0x1FFFFF
    disp -= (disp & 0x100000) << 1
    return (site & ~31) + 4 * disp


def b_target(addr, word):
    """b .S2 label: 21-bit word displacement from the fetch packet."""
    disp = word >> 7 & 0x1FFFFF
    disp -= (disp & 0x100000) << 1
    return (addr & ~31) + 4 * disp


@pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")
def test_bytes_match_assembly_sources():
    assert asm.assemble(ROOT / SEC["source"], BASE, whole_packets=True) == _data(SEC)
    for w in PATCH["write"]:
        if "source" in w:
            code, data = asm.assemble(ROOT / w["source"], w["addr"]), _data(w)
            assert data == code + b"\0" * (len(data) - len(code)), w["source"]


def test_slot_loop_jumps_to_the_engine():
    assert JUMP["expect"] == PROBE_CHAIN["write"][0]["expect"]     # the stock packet, as the probe hooks it
    assert far_target(JUMP["data"]) == BASE + VEC["engine"]
    data = _data(JUMP)
    assert len(data) == 32 and data[16:] == b"\0" * 16              # a whole plain packet: no stale header
    assert all(_word(data, i) & 1 == 0 for i in range(8))


def test_vectors_point_at_their_handlers():
    data = _data(SEC)
    for off in VEC.values():
        w = _word(data, off // 4)
        assert w & 0x7F == 0x12 and _word(data, off // 4 + 1) == 0x8000   # b .S2 ; nop 5
        assert BASE + 288 <= b_target(BASE + off, w) < BASE + len(data)   # into the code
    assert data[72:120] == b"\0" * 48


def test_callp_sites_reach_their_vectors():
    sites = {0xC00B8964: "unpack_live", 0xC00AE2EC: "unpack_saved", 0xC00AE680: "pack_dump",
             0xC00A7E50: "dirty", 0xC00A7FD8: "dirty", 0xC00ACD88: "dirty"}
    stock = {0xC00B8964: 0xC00B8294, 0xC00AE2EC: 0xC00B8294, 0xC00AE680: 0xC00B8474}
    for site, name in sites.items():
        old, new = (int.from_bytes(bytes.fromhex(WRITES[site][k]), "little") for k in ("expect", "data"))
        assert callp_target(site, old) == stock.get(site, 0xC00B8534)
        assert callp_target(site, new) == BASE + VEC[name]
        assert old & ~0x0FFFFF80 == new & ~0x0FFFFF80               # same op, same p-bit


def test_save_packet_jumps_to_rec_save():
    w = WRITES[0xC00B84C0]
    assert far_target(w["data"]) == BASE + VEC["rec_save"]
    old, new = _data({"data": w["expect"]}), _data(w)
    assert new[16:28] == old[16:28]                                  # 0xC00B84D0's first three words, unchanged
    assert _word(old, 7) >> 28 == 0xE and _word(new, 7) == 0         # header replaced by a nop: plain packet


def test_screen_15_tables_and_cc_link():
    assert int.from_bytes(bytes.fromhex(WRITES[0xC00EEFD8]["data"]), "little") == BASE + VEC["keys"]
    assert int.from_bytes(bytes.fromhex(WRITES[0xC00EEBEC]["data"]), "little") == BASE + VEC["draw"]
    cc = WRITES[0xC00F2818]
    assert far_target(cc["expect"]) == 0xC00F2020 and far_target(cc["data"]) == BASE + VEC["cc"]
    handler = [s for s in MIDI_CC["section"] if s["addr"] == 0xC00F2800][0]
    assert _data(handler)[0x18:0x20].hex() == cc["expect"]


def test_auto_save_hook_retargets_tempo_hold():
    w = WRITES[0x1181FF80]
    hold2 = [s for s in patcher.load(ROOT / "patches/tempo-hold.yaml")["section"] if s["addr"] == 0x1181FF20][0]
    assert _data(hold2)[0x60:0x68].hex() == w["expect"]
    assert far_target(w["expect"]) == 0xC00B8534 and far_target(w["data"]) == BASE + VEC["dirty"]


def test_poll_trampoline_chains_through_the_mixer():
    w = WRITES[0xC00C82D0]
    clock = [x for x in patcher.load(ROOT / "patches/midi-clock.yaml")["write"] if x["addr"] == 0xC00C82D0][0]
    assert w["expect"] == clock["data"] and far_target(clock["data"]) == 0x1181E800   # midi-clock's, to poll.S
    assert far_target(w["data"]) == BASE + VEC["poll"]
    assert ".equ    POLL, 0x1181E800" in (ROOT / "asm/mixer/mixer.S").read_text()      # the mixer poll goes on there


def test_menu_writes_match_the_settings_section():
    sec = [s for s in SETTINGS["section"] if s["addr"] == 0x1181EA00][0]
    sb = _data(sec)
    for addr in (0x1181EF78, 0x1181F0B0, 0x1181F0F0):
        w = WRITES[addr]
        assert sb[addr - 0x1181EA00:][:len(bytes.fromhex(w["expect"]))].hex() == w["expect"]
    assert far_target(WRITES[0x1181EF78]["data"]) == BASE + MENU6
    menu = sb[0x1181EB80 - 0x1181EA00:][:20]                         # settings.S menu_names
    menu6 = _data(SEC)[MENU6:MENU6 + 24]
    assert menu6[:16] == menu[:16] and menu6[20:] == menu[16:]       # stock + MIDI, MIXER, version


def test_data_block():
    data = _data(SEC)
    assert data[LAYOUT:LAYOUT + 8] == bytes(8) and data[MAIL:MAIL + 8] == bytes(8)
    defaults = data[DEFAULTS:DEFAULTS + 12]
    assert defaults[0] == 0 and defaults[11] == MAGIC               # Serial, settings present
    assert data[LIVE:LIVE + 12] == defaults == data[SAVED:SAVED + 12]
    maxes = data[MAXES:MAXES + 12]
    assert all(d <= m for d, m in zip(defaults[:11], maxes))
    pages = data[PAGES:PAGES + 24]
    used = sorted(p for p in pages if p != 255)
    assert used == list(range(11))                                   # every setting on exactly one knob


def test_m2_build_does_not_overlap():
    sections = sorted(s for s in _spans(M2_SET) if not s[2].endswith("write"))
    for (_, end, a), (start, _, b) in zip(sections, sections[1:]):
        assert end <= start, f"{a} and {b} overlap at 0x{start:08X}"
    others = [s for s in _spans(M2_SET) if s[2] != "mixer-m2" and not s[2].endswith("write")]
    for a, e, _ in _spans(["mixer-m2"]):                            # the mixer writes only where it hooks
        hit = [p for s, t, p in others if s < e and a < t]
        assert hit in ([], ["midi-cc"], ["midi-settings"], ["tempo-hold"]), hex(a)
    other_writes = [s for s in _spans(M2_SET) if s[2].endswith("write") and s[2] != "mixer-m2 write"]
    for a, e, _ in _spans(["mixer-m2"]):                            # no write that another patch also makes
        hit = [p for s, t, p in other_writes if s < e and a < t]
        assert hit in ([], ["midi-clock write"] if a == 0xC00C82D0 else []), hex(a)   # the poll trampoline, chained
    assert BASE + len(_data(SEC)) <= 0xC0102000                     # inside the 64 KB MOD code area (looper buffer above)


def _spans(names):
    for p in names:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        for s in patch.get("section", []):
            yield s["addr"], s["addr"] + len(_data(s)), p
        for w in patch.get("write", []):
            yield w["addr"], w["addr"] + len(bytes.fromhex(w["data"])), p + " write"


def test_save_buf_is_the_stock_live_save_buffer():
    # Needs Zoom's MS-70CDR 2.10 updater (never committed): MIDISTOMP_70CDR_UPDATER=path
    import os
    import re
    from zoomms import ais, parts
    path = Path(os.environ.get("MIDISTOMP_70CDR_UPDATER", ROOT / "MS-70CDR_v2.10_Win_E/ZOOM MS-70CDR v2.10 Updater.exe"))
    if not path.is_file():
        pytest.skip("no MS-70CDR updater")
    os_part = next(p for p in parts.find_parts(path) if p.resource_id == 129)
    img = ais.parse(parts.read_part(path, os_part))
    lo, hi = (int.from_bytes(img.read(a, 4), "little") >> 7 & 0xFFFF for a in (0xC00B84D8, 0xC00B84E0))
    stock = hi << 16 | lo                                            # 0xC00B84D0: mvk / mvkh of the buffer it packs into
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    assert int(re.search(r"\.equ\s+SAVE_BUF,\s*(0x[0-9A-Fa-f]+)", src).group(1), 16) == stock
