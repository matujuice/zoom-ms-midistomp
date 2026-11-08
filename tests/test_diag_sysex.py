"""The MIDISTOMP SysEx receiver in asm/diag/diag.c, compiled for the host with gcc: the
pedal's addresses are swapped for test variables, the parser and replies are the real code."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOST = {"MIDI_BYTE", "MIDI_SEND", "TRANSPORT_MAGIC", "SERVICES_MAGIC", "R50_ENT"}

HARNESS = r"""
#include <stdio.h>
static void send(const unsigned char *m, int n) { for (int i = 0; i < n; i++) printf("%02X ", m[i]); printf("\n"); }
#define MIDI_SEND send
static unsigned transport = 0x5A4D5401u, services;
#define TRANSPORT_MAGIC transport
#define SERVICES_MAGIC services
static unsigned char r50[24 + 16 * 50];
#define R50_ENT(n) (r50 + 24 + 16 * (n))
#define STAMP(i) "V2.0.1"
@BLOCK@
int main(void)
{
    unsigned b;
    for (int i = 0; i < 16; i++) r50[24 + 16 * 3 + i] = (i * 37 + 200) & 255;
    while (scanf("%x", &b) == 1) if (sx_n || b == 0xF0) sx_byte(b);
    return 0;
}
"""


def unpack7(d):
    out = []
    for i in range(0, len(d), 8):
        out += [d[i + j] | (0x80 if d[i] & (0x40 >> (j - 1)) else 0) for j in range(1, min(8, len(d) - i))]
    return out


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("no gcc")
    src = (ROOT / "asm/diag/diag.c").read_text()
    block = src[src.index("/* ---- MIDISTOMP SysEx"):src.index("void diag_mend")]
    block = "\n".join(l for l in block.splitlines() if not re.match(r"#define (%s)\b" % "|".join(HOST), l))
    d = tmp_path_factory.mktemp("sx")
    (d / "t.c").write_text(HARNESS.replace("@BLOCK@", block))
    subprocess.run(["gcc", "-std=c99", "-o", str(d / "t.exe"), str(d / "t.c")], check=True)
    return d / "t.exe"


def run(exe, *msgs):
    text = " ".join(msgs)
    out = subprocess.run([str(exe)], input=text, capture_output=True, text=True, check=True).stdout
    return [bytes.fromhex(l) for l in out.splitlines()]


HELLO = "F0 7D 4D 53 54 01 2A F7"


def test_hello(exe):
    v, s = run(exe, HELLO)
    assert v == bytes.fromhex("F07D4D5354412A020001F7")
    f = s[7] | s[8] << 7 | s[9] << 14
    assert s[:7] == bytes.fromhex("F07D4D5354422A") and s[-1] == 0xF7 and len(s) == 12
    assert f & 2 and not f & 16 and f & (1 << 9) and s[10] == 0x7F
    assert all(b < 0x80 for b in s[1:-1])


def test_settings(exe):
    (r,) = run(exe, "F0 7D 4D 53 54 02 05 03 F7")
    assert r[:8] == bytes.fromhex("F07D4D5354430503") and r[-1] == 0xF7 and len(r) == 28
    assert all(b < 0x80 for b in r[1:-1])
    assert unpack7(list(r[8:-1])) == [(i * 37 + 200) & 255 for i in range(16)]


def test_ignored(exe):
    assert run(exe,
               "F0 7D 4D 53 54 02 05 32 F7",        # patch 50: no such entry
               "F0 7D 4D 53 55 01 00 F7",           # other signature
               "F0 52 00 61 33 F7",                 # stock Zoom message
               "F0 7D 4D 53 54 09 00 F7",           # unknown command
               "F0 7D 4D 53 54 01 00 00 00 00 F7",  # too long
               "F0 7D 4D 53 54 01 F7",              # no nonce
               "F0 7D 4D 53 54 01 00 90 40 F7") == []   # a status byte inside aborts it


def test_realtime_inside_and_restart(exe):
    # clock bytes inside the message are skipped; a new F0 restarts the message
    out = run(exe, "F0 7D 4D F0 7D 4D F8 53 54 01 F8 2A FA F7", "90 40 7F", HELLO)
    assert len(out) == 4 and out[0][6] == 0x2A and out[2][6] == 0x2A
