"""Host check of knob_step() (asm/mixer/pages.c), the C port of the stock knob step 0xC00ABE58: the real C,
with a fake clock in place of the stock ticks, against the stock math worked by hand."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

HOST = r"""
#include <stdio.h>
static int now, last_ev = -1, last_t;
#define KS_TICKS() now
#define KS_DIV(a, b) ((a) / (b))
#define KS_LAST last_ev
#define KS_TIME last_t
"""

DRIVER = r"""
static int turn(int ev, int steps, int range, int dt) { int s; now += dt; s = knob_step(ev, steps, range); last_ev = ev; return s; }
int main(void) {
    printf("%d ", turn(160, 1, 100, 1000));    /* first turn after another event: plain */
    printf("%d ", turn(160, 1, 100, 500));     /* slow: plain */
    printf("%d ", turn(160, 1, 100, 10));      /* 10 ms: 11 * 100 / 150 = 7 */
    printf("%d ", turn(160, -2, 100, 10));     /* 5 ms per detent: 16 * -2 * 100 / 150 = -21 */
    printf("%d ", turn(160, 1, 1, 5));         /* on / off: 16 / 150 = 0 -> the plain step */
    printf("%d ", turn(161, 1, 100, 5));       /* another knob: plain */
    printf("%d ", turn(161, 1, 1000, 1000));   /* slow: plain, time kept */
    printf("%d ", turn(161, 1, 1000, 5));      /* range > 500, under 8 ms: 16 * 1000 / 200 = 80 */
    printf("%d ", turn(161, 1, 1000, 10));     /* under 13 ms: 11 * 1000 / 1000 = 11 */
    printf("%d ", turn(161, 1, 1000, 15));     /* under 20 ms: 6 * 1000 / 3000 = 2 */
    printf("%d\n", turn(161, 1, 1000, 30));    /* slow: plain */
    return 0;
}
"""


def _cc():
    if subprocess.run([sys.executable, "-m", "ziglang", "version"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "ziglang", "cc"]
    return [shutil.which(n) for n in ("clang", "gcc") if shutil.which(n)][:1] or None


def test_knob_step_matches_stock(tmp_path):
    cc = _cc()
    if not cc:
        pytest.skip("no host C compiler")
    src = (ROOT / "asm/mixer/pages.c").read_text()
    fn = src[src.index("int knob_step(int ev"):src.index("/* Screen 15 key entry")]
    (tmp_path / "ks.c").write_text(HOST + fn + DRIVER)
    exe = tmp_path / "ks.exe"
    subprocess.run(cc + [str(tmp_path / "ks.c"), "-o", str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["1", "1", "7", "-21", "1", "1", "1", "80", "11", "2", "1"], out
