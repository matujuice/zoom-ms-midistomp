"""Host check of the PERFORM grid (asm/perform/perform_engine.c grid()): the real C with a fake MIDI transport
block. The 96-beat turns are worked out once per clock and cached (v2.0.3); the beat must still follow the clock
across the 2304-clock turns, through blocks that hold a clock, and back to bar 1 on MIDI Start."""
import subprocess
from pathlib import Path

import pytest

from tests.test_knob_step import _cc

ROOT = Path(__file__).resolve().parent.parent

HOST = r"""
#include <stdio.h>
#include "perform.h"
#define DU_BPM 2.4187211e-5f
static unsigned zt[6] = { 0x5A4D5401u, 0, 1, 0, 0, 12000 };   /* magic, seq, running, starts, clocks, BPM x 100 */
#define ZT ((volatile const unsigned *)zt)
PerfGrid perf_grid;
volatile int perf_on;
void perf_reset(void) {}
"""

DRIVER = r"""
int main(void) {
    unsigned c, b, bad = 0;
    for (c = 1; c <= 7000; c++) {                 /* three 96-beat turns, 4 blocks a clock */
        zt[4] = c;
        for (b = 0; b < 4; b++) { grid(); if (perf_grid.beat != (int)((c - 1) / 24)) bad++; }
    }
    zt[3]++; zt[4] = 1; grid();                    /* MIDI Start: bar 1 again */
    printf("%u %d\n", bad, perf_grid.beat);
    return 0;
}
"""


def test_grid_follows_the_clock_across_turns_and_start(tmp_path):
    cc = _cc()
    if not cc:
        pytest.skip("no host C compiler")
    src = (ROOT / "asm/perform/perform_engine.c").read_text(encoding="utf-8")
    fn = src[src.index("/* ---- Grid"):src.index("/* ---- Targets")]
    (tmp_path / "grid.c").write_text(HOST + fn + DRIVER, encoding="utf-8")
    exe = tmp_path / "grid.exe"
    subprocess.run(cc + ["-I", str(ROOT / "asm/perform"), str(tmp_path / "grid.c"), "-o", str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["0", "0"], out
