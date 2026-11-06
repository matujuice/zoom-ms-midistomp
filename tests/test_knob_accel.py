"""Host check of knob_accel() (asm/mixer/pages.c, SETTINGS > KNOB ACCEL): the real C, built with a host compiler."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

DRIVER = r"""
#include <stdio.h>
static int st[4] = {0, 0, -100000, 0}, t;
static int run(int gap, int n, int per) { int s = 0; while (n--) s += knob_accel(st, per, t += gap); return s; }
int main(void) {
    printf("%d ", knob_accel(st, 1, 0));                 /* 1 detent from rest */
    t = 5000; printf("%d ", run(200, 8, 1));             /* slow: 1 step per detent */
    t = 10000; run(16, 12, 4); printf("%d ", knob_accel(st, 4, t += 16));   /* flick: capped at 8 per detent */
    printf("%d\n", knob_accel(st, -1, t += 16));          /* turned back: slow again, 1 step */
    return 0;
}
"""


def _cc():
    if subprocess.run([sys.executable, "-m", "ziglang", "version"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "ziglang", "cc"]
    return [shutil.which(n) for n in ("gcc", "clang") if shutil.which(n)][:1] or None


def test_knob_accel_steps(tmp_path):
    cc = _cc()
    if not cc:
        pytest.skip("no host C compiler")
    src = (ROOT / "asm/mixer/pages.c").read_text()
    fn = src[src.index("#define KA_MAX"):src.index("/* Screen 15 key entry")]
    (tmp_path / "ka.c").write_text(fn + DRIVER)
    exe = tmp_path / "ka.exe"
    subprocess.run(cc + [str(tmp_path / "ka.c"), "-o", str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["1", "8", "32", "-1"], out
