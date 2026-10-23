import importlib.util
import re
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
       "rec_save": 40, "keys": 48, "draw": 56, "cc": 64, "mv_swap": 96, "mv_add": 104,
       "mv_delete": 112, "poll": 120}
UI, GAINS, PEDAL, MENUSCR, MENU7, LIVE, SAVED, PREV, MAXES, DEFAULTS = 136, 144, 176, 184, 196, 224, 248, 272, 296, 320
NSET = 24                                                            # chain.h: 24 settings (12-17: the buses)
CODE = 344                                                          # the code after the data block
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
        assert BASE + CODE <= b_target(BASE + off, w) < BASE + len(data)  # into the code
    assert data[72:96] == b"\0" * 24


def test_callp_sites_reach_their_vectors():
    sites = {0xC00B8964: "unpack_live", 0xC00AE2EC: "unpack_saved", 0xC00AE680: "pack_dump",
             0xC00A7E50: "dirty", 0xC00A7FD8: "dirty", 0xC00ACD88: "dirty"}
    stock = {0xC00B8964: 0xC00B8294, 0xC00AE2EC: 0xC00B8294, 0xC00AE680: 0xC00B8474}
    for site, name in sites.items():
        old, new = (int.from_bytes(bytes.fromhex(WRITES[site][k]), "little") for k in ("expect", "data"))
        assert callp_target(site, old) == stock.get(site, 0xC00B8534)
        assert callp_target(site, new) == BASE + VEC[name]
        assert old & ~0x0FFFFF80 == new & ~0x0FFFFF80               # same op, same p-bit


def test_effect_move_add_delete_reach_their_vectors():
    # the only callers of the stock swap, add and delete (dis6x of the 2.10 OS, research doc "M3a hooks")
    sites = {0xC00B76A4: ("mv_swap", 0xC00B6BC4), 0xC00A7BE0: ("mv_add", 0xC00C22F4),
             0xC00A8294: ("mv_delete", 0xC00C2030)}
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    for site, (name, stock) in sites.items():
        old, new = (int.from_bytes(bytes.fromhex(WRITES[site][k]), "little") for k in ("expect", "data"))
        assert callp_target(site, old) == stock
        assert callp_target(site, new) == BASE + VEC[name]
        assert old & ~0x0FFFFF80 == new & ~0x0FFFFF80               # same op, same p-bit
        assert re.search(rf"\.equ\s+FX_\w+,\s*0x{stock:08X}\b", src)    # the wrapper goes on to stock


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
    looper = [x for x in patcher.load(ROOT / "patches/looper.yaml")["write"] if x["addr"] == 0xC00C82D0][0]
    assert w["expect"] == [clock["data"], looper["data"]] and far_target(clock["data"]) == 0x1181E800   # midi-clock's, to poll.S
    assert far_target(w["data"]) == BASE + VEC["poll"]
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    assert ".equ    POLL, 0x1181E800" in src                                         # the mixer poll goes on there,
    assert f".equ    LP_POLL, 0x{far_target(looper['data']):08X}" in src             # or to the looper's poll_pre


def test_menu_writes_match_the_settings_section():
    sec = [s for s in SETTINGS["section"] if s["addr"] == 0x1181EA00][0]
    sb = _data(sec)
    for addr in (0x1181EF78, 0x1181F0B0, 0x1181F0F0, 0x1181F27C):
        w = WRITES[addr]
        assert sb[addr - 0x1181EA00:][:len(bytes.fromhex(w["expect"]))].hex() == w["expect"]
    assert far_target(WRITES[0x1181EF78]["data"]) == BASE + MENU7
    assert far_target(WRITES[0x1181F0F0]["data"]) == BASE + MENUSCR
    menu = sb[0x1181EB80 - 0x1181EA00:][:20]                         # settings.S menu_names
    m7 = _data(SEC)[MENU7:MENU7 + 28]
    stock = [menu[4 * i:4 * i + 4] for i in range(5)]
    got = [m7[4 * i:4 * i + 4] for i in range(5)]
    assert got[:2] + got[3:] == stock[:3] + stock[4:]                # stock without MIDI; PERFORM MODE 2
    got.append(m7[20:24])
    got.append(m7[24:28])
    sec = _data(SEC)
    assert sec[MENUSCR + 2:MENUSCR + 8] == bytes([11, 1, 9, 11, 11, 0])   # PERFORM, SETTINGS (stock row 2), version, MASTER, KALEIDO
    for i, name in ((2, b"PERFORM MODE\0"), (5, b"MASTER\0"), (6, b"KALEIDO\0")):
        off = _word(got[i]) - BASE
        assert sec[off:off + len(name)] == name


def test_data_block():
    data = _data(SEC)
    # chain.h UI bytes: CUR, SEL, BUSROW = A, DELP, ADDBUS = none, FROMCHAIN, PFIRST, PLAST = every node page (PG_OUT)
    assert data[UI:UI + 8] == bytes([0, 0, 1, 0, 0xFF, 0, 0, 6])
    assert data[GAINS + 20:GAINS + 24] == bytes.fromhex("0000803f")  # limiter gain 1.0
    assert data[PEDAL] == 0 and PEDAL < MENUSCR                        # MONO until pedal_in.c unpacks
    assert MENUSCR + 7 <= MENU7 and MENU7 + 28 <= LIVE and LIVE + NSET <= SAVED and SAVED + NSET <= PREV
    assert PREV + NSET <= MAXES and MAXES + NSET <= DEFAULTS and DEFAULTS + NSET <= CODE
    defaults = data[DEFAULTS:DEFAULTS + NSET]
    assert defaults[0] == 0 and defaults[11] == MAGIC               # Serial, settings present
    assert defaults[12:18] == bytes(6)                               # every bus PRE
    assert defaults[18:] == bytes([100, 100, 0, 0, 0, 0])            # Input R, Master R unity; Stereo, no Mute / Solo
    assert data[LIVE:LIVE + NSET] == defaults == data[SAVED:SAVED + NSET]
    maxes = data[MAXES:MAXES + NSET]
    assert all(d <= m for d, m in zip(defaults, maxes)) and maxes[12:18] == bytes([3] * 6)   # PRE A B POST
    assert maxes[0] == 3 and maxes[18:] == bytes([150, 150, 2, 1, 1, 2])
    h = (ROOT / "asm/mixer/chain.h").read_text()                    # the C reads the same offsets
    for name, off in {"SHOWN": 78, "PEDAL": PEDAL, "LIVE": LIVE}.items():
        assert re.search(rf"#define {name} .*MIXER_BASE \+ {off}\)", h), name
    assert f"#define NSET {NSET}" in h


def test_cc_map_covers_85_to_101():
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    eq = {n: int(v) for n, v in re.findall(r"\.equ\s+(S_\w+),\s*(\d+)", src)}
    h = (ROOT / "asm/mixer/chain.h").read_text()
    for n, v in eq.items():                                          # same numbers as the C
        assert re.search(rf"#define {n} {v}\b", h), n
    rows = re.search(r"cc_map:((?:\s*\.byte[^\n]*\n)+)", src).group(1)
    names = [x.strip() for x in re.sub(r"\.byte", ",", rows).split(",") if x.strip()]
    assert names[:17] == ["S_SEND", "S_XF", "S_MASTER", "S_IN", "S_RA", "S_RB", "S_MA", "S_MB", "S_MODE",
                          "S_CURVE", "S_PHASE", "S_INR", "S_MR", "S_OUT", "S_MUTEA", "S_MUTEB", "S_SOLO"]
    assert "CC_FIRST, 85" in src and re.search(r"mvk\s+\.S1\s+16, a0\s+cmpgtu", src)   # 85 + 16 = 101


CSEC = PATCH["section"][1]                                           # M3b: chain_vec.asm + chain_keys.c + chain_draw.c
CVEC = {"keys": 0, "draw": 8, "chain_poll": 16, "s33_keys": 24,
        "settings_key": 32, "settings_draw": 40, "settings_pack": 48, "settings_unpack": 56,
        "engine_run": 64, "mix_get": 72, "mix_put": 80, "pages_key": 88, "pages_draw": 96,
        "ab_tag": 104, "r50_load": 112, "r50_save": 120, "perf_keys": 128, "perf_draw": 136,
        "midi_key": 144, "midi_draw": 152}
CMIX = {"C_POLL": "chain_poll", "C_ENGINE": "engine_run", "C_GET": "mix_get", "C_PUT": "mix_put",
        "C_KEYS": "pages_key", "C_DRAW": "pages_draw"}                # mixer.S names for them


def test_chain_section_vectors():
    data = _data(CSEC)
    assert CSEC["addr"] == 0xC00F8000 and CSEC["source"] == "asm/mixer/chain_keys.c"
    assert BASE + len(_data(SEC)) <= CSEC["addr"] and CSEC["addr"] + len(data) <= 0xC0106DC0   # after mixer.S, below R50_COPY
    for off in CVEC.values():
        w = _word(data, off // 4)
        assert w & 0x7F == 0x12 and _word(data, off // 4 + 1) == 0x8000   # b .S2 ; nop 5
        assert CSEC["addr"] + 8 * len(CVEC) <= b_target(CSEC["addr"] + off, w) < CSEC["addr"] + len(data)
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    assert re.search(rf"\.equ\s+C_SEC,\s*0x{CSEC['addr']:08X}\b", src)
    for name, vec in CMIX.items():
        assert re.search(rf"\.equ\s+{name},\s*C_SEC \+ {CVEC[vec]}\b", src), name


def test_chain_screen_hooks():
    tables = {0xC00EEFA8: (0xC00A83A0, "keys"), 0xC00EEBBC: (0xC00A93F0, "draw")}   # screen 3 entries, stock stubs
    for addr, (stock, name) in tables.items():
        w = WRITES[addr]
        assert int.from_bytes(bytes.fromhex(w["expect"]), "little") == stock
        assert int.from_bytes(bytes.fromhex(w["data"]), "little") == CSEC["addr"] + CVEC[name]
    callps = {0xC00A832C: (0xC00A7A6C, "s33_keys"), 0xC00CB284: (0xC00BB92C, "ab_tag")}
    for site, (stock, name) in callps.items():
        old, new = (int.from_bytes(bytes.fromhex(WRITES[site][k]), "little") for k in ("expect", "data"))
        assert callp_target(site, old) == stock
        assert callp_target(site, new) == CSEC["addr"] + CVEC[name]
        assert old & ~0x0FFFFF80 == new & ~0x0FFFFF80               # same op, same p-bit


def test_perform_screen_11_hooks():
    tables = {0xC00EEFC8: (0xC00A8310, "perf_keys"), 0xC00EEBDC: (0xC00A9398, "perf_draw")}   # free screen 11, stock stubs
    for addr, (stock, name) in tables.items():
        w = WRITES[addr]
        assert int.from_bytes(bytes.fromhex(w["expect"]), "little") == stock
        assert int.from_bytes(bytes.fromhex(w["data"]), "little") == CSEC["addr"] + CVEC[name]
    hdr = (ROOT / "asm/perform/perform.h").read_text()
    assert re.search(r"#define PT_SIZE 112\s", hdr)                 # 50 of them in record 50 (R50_SIZE)
    build = (ROOT / "scripts/build_mixer_ui.py").read_text()
    for f in ("perform_engine.c", "perform_store.c", "perform_keys.c", "perform_draw.c"):
        assert f in build and (ROOT / "asm/perform" / f).exists()


def test_record_50_holds_the_settings_table():
    hdr = (ROOT / "asm/mixer/chain.h").read_text()
    r50, copy = (int(re.search(rf"#define {n}\D*(0x[0-9A-Fa-f]+)", hdr).group(1), 0) for n in ("R50", "R50_COPY"))
    assert re.search(r"#define R50_SIZE \(824 \+ 4 \+ 50 \* 112\)", hdr)
    size = 24 + 16 * 50 + 4 + 50 * 112                               # stock globals, a mixer entry per patch, Perform
    end = CSEC["addr"] + len(_data(CSEC))
    assert end <= copy and copy + size <= r50 and r50 + size <= 0xC010A000   # above the C section, below the looper
    assert re.search(rf"\.equ\s+R50,\s*0x{r50:08X}", (ROOT / "asm/mixer/mixer.S").read_text())
    table = WRITES[0xC00EA9A8]                                       # record size table, entry 50
    assert (table["expect"], table["data"]) == ("18000000", size.to_bytes(4, "little").hex())
    w = {(a, k): int.from_bytes(bytes.fromhex(WRITES[a][k]), "little") for a in (0xC00B48C0, 0xC00B48C8) for k in ("expect", "data")}
    cst = lambda a, k: w[(a, k)] >> 7 & 0xFFFF
    assert cst(0xC00B48C8, "expect") << 16 | cst(0xC00B48C0, "expect") == 0xC009D7D0   # compaction buffer, stock
    assert cst(0xC00B48C8, "data") << 16 | cst(0xC00B48C0, "data") == copy
    assert cst(0xC00B48C0, "data") < 0x8000                          # mvk sign-extends
    for a in (0xC00B48C0, 0xC00B48C8):
        assert w[(a, "expect")] & ~(0xFFFF << 7) == w[(a, "data")] & ~(0xFFFF << 7)
    callps = {0xC00BA798: (0xC00B4AAC, "r50_load"), 0xC00BA3F8: (0xC00B49F4, "r50_save")}
    for site, (stock, name) in callps.items():
        old, new = (int.from_bytes(bytes.fromhex(WRITES[site][k]), "little") for k in ("expect", "data"))
        assert callp_target(site, old) == stock
        assert callp_target(site, new) == CSEC["addr"] + CVEC[name]
        assert old & ~0x0FFFFF80 == new & ~0x0FFFFF80


PEDAL_HOOKS = {0xC00EEFA0: "settings_key", 0xC00EEBB4: "settings_draw",      # screen 1 table entries
               0xC00B9EC8: "settings_pack", 0xC00BD9E4: "settings_unpack",  # settings.S trampolines
               0xC00EEFD4: "midi_key", 0xC00EEBE8: "midi_draw"}              # screen 14 table entries


def test_pedal_input_hooks():
    ms = {w["addr"]: w for w in patcher.load(ROOT / "patches/midi-settings.yaml")["write"]}
    for addr, name in PEDAL_HOOKS.items():
        w = WRITES[addr]
        assert w["expect"] == ms[addr]["data"]                          # on top of midi-settings
        data = bytes.fromhex(w["data"])
        if len(data) == 4:
            assert int.from_bytes(data, "little") == CSEC["addr"] + CVEC[name]
        else:                                                           # mvkl/mvkh b0, then as midi-settings
            lo, hi = (_word(data, i) >> 7 & 0xFFFF for i in (0, 1))
            assert hi << 16 | lo == CSEC["addr"] + CVEC[name] and data[8:] == bytes.fromhex(w["expect"])[8:]


def test_pedal_input_names_settings_s_addresses():
    """pedal_in.c calls into settings.S by address: check them against midi-settings.yaml."""
    sec = next(s for s in patcher.load(ROOT / "patches/midi-settings.yaml")["section"] if s["addr"] == 0x1181EA00)
    d = _data(sec)
    w = lambda a: _word(d, (a - sec["addr"]) // 4)
    bt = lambda a: b_target(a, w(a))
    mvk = lambda a: (w(a + 4) >> 7 & 0xFFFF) << 16 | w(a) >> 7 & 0xFFFF
    draw = bt(sec["addr"] + 88)                                         # settings_draw
    keys = bt(bt(sec["addr"] + 80) + 12)                                # settings_keys_e's branch
    want = {"SETTINGS_ICONS": mvk(draw + 28),
            "DRAW_LIST": bt(draw + 48), "SETTINGS_KEYS": keys,
            "PACK_HOOK": sec["addr"] + 128, "UNPACK_HOOK": sec["addr"] + 136}
    src = (ROOT / "asm/mixer/pedal_in.c").read_text()
    for name, addr in want.items():
        assert re.search(rf"#define {name} .*0x{addr:08X}\b", src), name


def test_sections_match_a_fresh_ti_build():
    spec = importlib.util.spec_from_file_location("build_mixer_ui", ROOT / "scripts" / "build_mixer_ui.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    if not b.available():
        pytest.skip("TI CGT not installed (TI_CGT)")
    assert b.assemble(ROOT / SEC["source"], BASE) == _data(SEC)
    assert b.build_c() == _data(CSEC)                                # also: links without RTS, no B14
    far = PATCH["section"][2]                                        # the C's zeroed variables
    assert (far["addr"], _data(far)) == (b.FAR_ADDR, bytes(-(-b.FAR_LEN // 32) * 32))


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
        chained = {0xC00C82D0: ["midi-clock write"]}                 # the poll trampoline
        chained.update(dict.fromkeys(PEDAL_HOOKS, ["midi-settings write"]))
        assert hit in ([], chained.get(a, [])), hex(a)
    assert BASE + len(_data(SEC)) <= 0xC0106DC0                     # inside the MOD code area (R50_COPY, R50, looper above)


def _spans(names):
    for p in names:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        for s in patch.get("section", []):
            yield s["addr"], s["addr"] + len(_data(s)), p
        for w in patch.get("write", []):
            yield w["addr"], w["addr"] + len(bytes.fromhex(w["data"])), p + " write"


def _stock_image():
    # Needs Zoom's MS-70CDR 2.10 updater (never committed): MIDISTOMP_70CDR_UPDATER=path
    import os
    from zoomms import ais, parts
    path = Path(os.environ.get("MIDISTOMP_70CDR_UPDATER", ROOT / "MS-70CDR_v2.10_Win_E/ZOOM MS-70CDR v2.10 Updater.exe"))
    if not path.is_file():
        pytest.skip("no MS-70CDR updater")
    os_part = next(p for p in parts.find_parts(path) if p.resource_id == 129)
    return ais.parse(parts.read_part(path, os_part))


def test_effect_hooks_expect_the_stock_image():
    img = _stock_image()
    for site in (0xC00B76A4, 0xC00A7BE0, 0xC00A8294, 0xC00EEFA8, 0xC00EEBBC, 0xC00A832C,
                 0xC00CB284):
        assert img.read(site, 4).hex() == WRITES[site]["expect"]


def test_save_buf_is_the_stock_live_save_buffer():
    img = _stock_image()
    lo, hi = (int.from_bytes(img.read(a, 4), "little") >> 7 & 0xFFFF for a in (0xC00B84D8, 0xC00B84E0))
    stock = hi << 16 | lo                                            # 0xC00B84D0: mvk / mvkh of the buffer it packs into
    src = (ROOT / "asm/mixer/mixer.S").read_text()
    assert int(re.search(r"\.equ\s+SAVE_BUF,\s*(0x[0-9A-Fa-f]+)", src).group(1), 16) == stock
