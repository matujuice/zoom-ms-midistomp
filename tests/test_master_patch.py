import importlib.util
import re
from pathlib import Path

import pytest

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/mixer-m2.yaml")
(SEC,) = [s for s in PATCH["section"] if s["addr"] == 0xC010A000]
VEC, END, BUF_END = 0xC010A000, 0xC0110400, 0xC0116000


def _data(sec):
    return bytes.fromhex("".join(sec["data"].split()))


def test_section_fits_below_the_buffers():
    assert VEC + len(_data(SEC)) <= END
    # the buffers end where the looper's region 1 starts (asm/looper/block.S)
    assert f"{BUF_END:#010X}"[2:] in (ROOT / "asm/looper/block.S").read_text().upper()
    assert f"MS_END    {BUF_END:#x}u".lower() in (ROOT / "asm/master/master.h").read_text().lower()


def test_vectors_and_flag():
    img = _data(SEC)
    if len(img) < 36:
        pytest.skip("MASTER not built yet")
    for off in (0, 8, 16, 24):                                       # B to the four functions
        word = int.from_bytes(img[off:off + 4], "little")
        assert word & 0x7C == 0x10, hex(word)                        # B disp (opcode 00100)
    assert img[32:36] == bytes(4)                                    # ms_on starts closed


def test_callers_use_the_vector_addresses():
    src = lambda p: (ROOT / p).read_text()
    assert re.search(r"MS_ON \(\*\(volatile int \*\)0xC010A020\)", src("asm/mixer/engine.c"))
    assert "0xC010A000)" in src("asm/mixer/engine.c")                 # master_tap
    perf = src("asm/perform/perform_engine.c")
    assert "0xC010A020" in perf and "0xC010A008)" in perf              # master_poll
    vec = src("asm/mixer/chain_vec.asm")
    assert "0xC010A010, A0" in vec and "0xC010A018, A0" in vec          # master_key, master_draw
    asm = src("asm/master/master_vec.asm")
    assert asm.index("master_tap") < asm.index("master_poll") < asm.index("master_key") < asm.index("master_draw")


def test_master_matches_a_fresh_ti_build():
    spec = importlib.util.spec_from_file_location("build_master_ui", ROOT / "scripts" / "build_master_ui.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    if not b.available():
        pytest.skip("TI CGT not installed (TI_CGT)")
    if not (ROOT / b.SOURCE).exists():
        pytest.skip("asm/master/master.c not written yet")
    assert b.build() == _data(SEC)                                   # also: no RTS, no B14, fits
