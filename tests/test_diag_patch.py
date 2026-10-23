import importlib.util
from pathlib import Path

import pytest

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/diag.yaml")
PROBE = patcher.load(ROOT / "patches/m0-probe.yaml")
(SEC,) = PATCH["section"]
VEC = 0xC00F3100


def callp_target(addr, data):                                       # as in test_looper_patch.py
    word = int.from_bytes(bytes.fromhex(data), "little")
    disp = word >> 7 & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp >> 20 else disp)


def _data(sec):
    return bytes.fromhex("".join(sec["data"].split()))


def _site(addr):
    return next(w for w in PATCH["write"] if w["addr"] == addr)


def test_hooks_call_the_diag_vectors():
    for addr, off in ((0xC00C6998, 8), (0xC00A93D0, 16), (0xC00A8364, 24), (0xC00A9398, 32),
                      (0xC00AECCC, 144), (0xC00AEEE0, 152)):
        w = _site(addr)
        assert callp_target(addr, w["data"]) == VEC + off
        if addr == 0xC00AECCC:                                      # an ldw before
            continue
        # only the displacement changes (the parallel bit of the key stub stays)
        mask = ~(0x1FFFFF << 7) & 0xFFFFFFFF
        assert int.from_bytes(bytes.fromhex(w["data"]), "little") & mask == \
            int.from_bytes(bytes.fromhex(w["expect"]), "little") & mask


def test_probe_hooks_and_dsp_limit_unchanged():
    probe = {w["addr"]: w for w in PROBE["write"]}
    for addr in (0xC00BB52C, 0xC00C6998, 0xC00A93D0, 0xC00A8364):
        assert _site(addr)["expect"] == probe[addr]["expect"]
    assert _site(0xC00BB52C)["data"] == probe[0xC00BB52C]["data"]


def test_section_layout():
    img = _data(SEC)
    assert img[40:44] == (0x47414944).to_bytes(4, "little")       # the magic engine.c checks
    for key, off in SEC["stamp"].items():
        assert img[off:off + 16].rstrip(b"\0") == f"<{key}>".encode()
    menu = _site(0xC00F60D4)
    name = int.from_bytes(bytes.fromhex(menu["data"]), "little") - VEC
    assert img[name:name + 7] == b"SYSTEM\0"
    assert VEC + len(img) <= 0xC00F5400                             # below lbox.c


def test_diag_matches_a_fresh_ti_build():
    spec = importlib.util.spec_from_file_location("build_diag_ui", ROOT / "scripts" / "build_diag_ui.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    if not b.available():
        pytest.skip("TI CGT not installed (TI_CGT)")
    assert b.build() == _data(SEC)                                   # also: no RTS, no B14, fits
