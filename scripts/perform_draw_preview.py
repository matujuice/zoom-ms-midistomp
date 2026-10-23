"""Host check for asm/perform/perform_draw.c and perform_keys.c: build them with a host C compiler
(gcc, clang, cl or `pip install ziglang`) against a fake LCD frame and fake stock knob / fader /
switch / tab primitives, draw the preview states and write each as <name>.png (4x, the mockup's
colors) plus <name>_mockup.png when Node is found: the same state drawn by docs/perform-ui-mockup.html's
own JavaScript (its FX parameters renamed Knob1 ... as the C names them). The pixel difference of
each pair is printed. It then runs the gesture and SETUP key checks on the host.

Usage: py scripts/perform_draw_preview.py [outdir]
Exit code 2 when no host C compiler is found, 1 when a check fails."""
import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PERF = ROOT / "asm/perform"
MOCKUP = ROOT / "docs/perform-ui-mockup.html"
BG, INK = (0xE2, 0xE5, 0xE8), (0x3A, 0x3C, 0x96)
EXTRA = ["C:/msys64/ucrt64/bin/gcc.exe", "C:/msys64/mingw64/bin/gcc.exe", "C:/mingw64/bin/gcc.exe",
         "C:/Program Files/LLVM/bin/clang.exe"]

# ---- the states: a control per row, the mockup's example patch (FX1 DELAY, FX2 TREMOLO, FX3 HALL, FX4 LOOPER) ----
NODE = {"IN InLvl": (88, 150), "ROUTE XFade": (85, 100), "ROUTE Mode": (93, 3), "ROUTE BusA": (89, 150), "ROUTE BusB": (90, 150),
        "MIX XFade": (86, 100), "MIX Outpt": (98, 2), "MIX Curve": (94, 2), "MIX MixA": (91, 150), "MIX MixB": (92, 150),
        "MIX PhasB": (95, 1), "MIX MuteA": (99, 1), "MIX MuteB": (100, 1), "MIX Solo": (101, 2), "OUT Mastr": (87, 150)}
UNUSED = None


def cc(t):
    if t == "OFF":
        return 255
    if t in NODE:
        return NODE[t][0]
    n, p = int(t[2]), t[4:]
    return 0x80 + n - 1 if p == "Ftsw" else 14 + 10 * (n - 1) + (0 if p == "OnOff" else int(p[4:]))


def mx(t):
    return NODE[t][1] if t in NODE else 1 if t.endswith(("OnOff", "Ftsw")) else 127


def disp(t, v):
    return (v * mx(t) + 63) // 127


def mv(v, n=0, l=0):
    return (v, n, l)


def base():
    s = dict(now=3625, cyc=4, status="EMPTY", pend={}, arm=None, screen="play", pos=0, ctl=1, ges=1, mv=1, pm=1, pp=0, ev=-1,
             targets=["MIX XFade", "FX3 Knob2", "FX2 Knob1", "FX1 Knob3", "FX2 OnOff", "OUT Mastr", "FX4 Ftsw"],
             values={"MIX XFade": 100, "FX3 Knob2": 38, "FX2 Knob1": 90, "FX1 Knob3": 50, "FX2 OnOff": 127, "OUT Mastr": 85, "FX4 Ftsw": 0})
    m = [[UNUSED] * 6 for _ in range(7)]            # [ctl][M_*]
    m[0][1] = mv(64, 5)
    m[1][:] = [mv(38, 11), mv(100), mv(38, 5), mv(110), mv(38), UNUSED]
    m[2][1:3] = [mv(127), mv(0, 5)]
    m[3][1:3] = [mv(115, 0, 10), mv(38, 6, 10)]
    m[4][1:3] = [mv(0), mv(127, 5)]
    m[5][1:3] = [mv(0, 0, 12), mv(85, 8, 13)]
    s["moves"] = m
    return s


def states():
    out = []

    def add(name, **kw):
        s = base()
        s.update(kw)
        out.append((name, s))
    add("play_idle")
    add("play_rec_in_a", arm=875, pend={6: 14, 1: 10, 3: 19})
    add("play_rec_in_b", now=3750, arm=750, pend={6: 12, 1: 8, 3: 17})
    add("play_recording", now=5300, status="REC 2")
    add("play_no_clock", now=-1)
    add("perform_menu", screen="menu", pos=1)
    add("setup_top", screen="top", pos=3)
    add("setup_control", screen="ctl", ctl=1, pos=2)
    add("setup_gestures", screen="ges", ctl=1, ges=1, pos=1)
    add("setup_move", screen="move", ctl=1, ges=1, mv=1)
    add("setup_move_lag", screen="move", ctl=3, ges=1, mv=2)
    add("setup_module", screen="pmod", ctl=1, pos=2)
    add("setup_param", screen="ppar", ctl=0, pm=7, pos=0)
    return out


# ---- the host side: fake LCD and stock primitives -----------------------------------------------
HOST_H = r'''#ifndef PERF_HOST_H
#define PERF_HOST_H
extern unsigned char host_lcd[1024];
extern int host_count, host_posts, host_fx[6][2], host_svc[32], host_screen;
extern const char *host_names[6];
const char *host_desc(int, int);
void host_knob(int, double, int, int);
void host_fader(int, int, int, int, int, int);
void host_toggle(int, int, int, int);
int host_tab(int, int, int, int, const char *);
void host_box(int, int, int, int, int);
#define LCD0 ((volatile unsigned *)host_lcd)
#define LCD_DIRTY(f) ((void)(f))
#define COUNT host_count
#define FX_REC(s) host_fx[s]
#define DSP_OFF 0
#define FX_NAME(s, p) host_desc(s, p)
#define SVC(i) host_svc[i]
#define EVENT_POST(a, b) (host_posts++)
#define SET_SCREEN(s, r) (host_screen = 100 * (s) + (r))
#define MAILBOX 0
#define KP_KNOB host_knob
#define KP_FADER host_fader
#define KP_TOGGLE host_toggle
#define KP_TAB host_tab
#define KP_BOX host_box
#define KP_DIVD(a, b) ((double)(a) / (double)(b))
#endif
'''

HOST_C = r'''#include <math.h>
#include <stdio.h>
#include <string.h>
#include "perform.h"
#include "perf_host.h"
unsigned char host_lcd[1024];
int host_count = 4, host_posts, host_fx[6][2], host_svc[32], host_screen;
const char *host_names[6] = { "DELAY", "TREMOLO", "HALL", "LOOPER", "REVERB", "CHORUS" };
static int host_d[6][11][12];
const char *host_desc(int s, int p)              /* descriptor entries: the name, then Knob1-9 (max 127, the last flagged) */
{
    int *d = host_d[s][p];
    if (p == 1) return host_names[s];
    sprintf((char *)d, "Knob%d", p - 1);
    d[3] = 127; d[11] = p == 10 ? 4 : 0;
    return (const char *)d;
}
PerfPatch perf_patch;
PerfGrid perf_grid;
volatile int perf_on;
static int host_val[256], host_pend[8];
int perf_value(int t) { return host_val[t & 255]; }
int perf_pending(int c) { return host_pend[c]; }
extern int pu_scr, pu_pos[8], pu_ctl, pu_ev, pu_ges, pu_mv, pu_mod;
#include "host_data.h"

static void hpx(int x, int y, int v)
{
    if (x < 0 || x > 127 || y < 0 || y > 63) return;
    if (v) host_lcd[(y >> 3) * 128 + x] |= 1 << (y & 7); else host_lcd[(y >> 3) * 128 + x] &= ~(1 << (y & 7));
}
static void hblit(int x, int y, int w, int h, const unsigned char *b)
{
    int r, c;
    for (r = 0; r < h; r++) for (c = 0; c < w; c++) hpx(x + c, y + r, b[(r >> 3) * w + c] >> (r & 7) & 1);
}
static void hline(int x0, int y0, int x1, int y1)    /* 0xC00A132C as the mockup ports it: horizontal, vertical and 45 degrees are all that is used */
{
    int x, y, t;
    if (x0 == x1 && y0 == y1) return;
    if (y0 == y1) { if (x0 > x1) { t = x0; x0 = x1; x1 = t; } for (x = x0; x <= x1; x++) hpx(x, y0, 1); return; }
    if (x0 == x1) { if (y0 > y1) { t = y0; y0 = y1; y1 = t; } for (y = y0; y <= y1; y++) hpx(x0, y, 1); return; }
    if (y0 > y1) { t = x0; x0 = x1; x1 = t; t = y0; y0 = y1; y1 = t; }
    for (y = y0; y <= y1; y++) hpx((x1 - x0) * y / (y1 - y0) + (x0 * y1 - x1 * y0) / (y1 - y0), y, 1);
}
static void hrect(int x0, int y0, int x1, int y1, int mode)
{
    int x, y;
    for (y = y0; y <= y1; y++) for (x = x0; x <= x1; x++) {
        int edge = x == x0 || x == x1 || y == y0 || y == y1;
        if (mode == 0) hpx(x, y, 1); else if (mode == 2) hpx(x, y, 0); else if (edge) hpx(x, y, 1); else if (mode == 1) hpx(x, y, 0);
    }
}
static void hinv(int x0, int y0, int x1, int y1)
{
    int x, y;
    for (y = y0; y <= y1; y++) for (x = x0; x <= x1; x++) if ((unsigned)x < 128 && (unsigned)y < 64) host_lcd[(y >> 3) * 128 + x] ^= 1 << (y & 7);
}
static void hfont7(const char *s, int x, int y)
{
    for (; *s; s++, x += 7) { int c = *s < 32 ? 0 : *s > 126 ? 94 : *s - 32; hblit(x, y, 7, 8, host_F7 + 7 * c); }
}
void host_box(int f, int x, int y, int w, int h)
{
    (void)f;
    hline(x, y, x + w - 1, y); hrect(x, y, x + 1, y + h - 1, 0); hrect(x + w - 2, y, x + w - 1, y + h - 1, 0);
}
void host_toggle(int f, int on, int x, int y) { (void)f; hblit(x, y, 31, 24, on ? host_TOG1 : host_TOG0); }
void host_fader(int f, int x, int y, int v, int lo, int hi)
{
    int h = 20 * (v - lo) / (hi - lo);
    (void)f;
    hblit(x, y, 31, 24, host_FAD);
    hrect(x + 6, y + 20 - h, x + 23, y + 22 - h, 1);
}
int host_tab(int f, int x, int y, int st, const char *s)   /* 0xC00AB238 */
{
    int w = 7 * (int)strlen(s) + 7;
    (void)f;
    hfont7(s, x + 4, y + 2);
    if (st == 0) {
        hline(x + 3, y, x, y + 3); hline(x + 4, y, x, y + 4); hline(x + w - 4, y, x + w - 1, y + 3); hline(x + w - 5, y, x + w - 1, y + 4);
        hline(x + 4, y, x + w - 5, y);
        hline(x, y + 4, x, y + 11); hline(x + 1, y + 4, x + 1, y + 11); hline(x + w - 2, y + 4, x + w - 2, y + 11); hline(x + w - 1, y + 4, x + w - 1, y + 11);
        hrect(x + 2, y + 11, x + w - 3, y + 11, 2);
    } else if (st == 1) {
        hline(x, y, x + w - 4, y); hline(x + 1, y + 1, x + w - 3, y + 1); hinv(x + 2, y + 2, x + w - 2, y + 9); hline(x + w - 1, y + 3, x + w - 1, y + 9);
    } else {
        hline(x + 3, y, x + w - 1, y); hline(x + 2, y + 1, x + w - 2, y + 1); hinv(x + 1, y + 2, x + w - 3, y + 9); hline(x, y + 3, x, y + 9);
    }
    return w;
}
static double rnd(double v) { return v < 0 ? -floor(-v + 0.5) : floor(v + 0.5); }
void host_knob(int f, double frac, int x, int y)   /* 0xC00A95A4, as the mockup ports it */
{
    double k = 40.0 / 33, C = 5 * M_PI / 4, D0 = 0.785398163395, D1 = 2.356194490185, D2 = 3.926990816975;
    double t, a, S, cs, tana, tanC, sC, ms;
    int cx = x + 14, cy = y + 10, i, A1;
    (void)f;
    hblit(x, y, 29, 20, host_KNOB);
    t = frac * 3 * M_PI * 0.5; a = C - t; S = 10 * sin(a); cs = 10 * cos(a);
    tana = cs != 0 ? S / cs : (S < 0 ? -1 : 1) * 1e300; tanC = tan(C); sC = 10 * sin(C);
#define Q(i) (tana != 0 ? (i) / tana : ((i) < 0 ? -1 : 1) * 1e300)
    for (i = (int)sC; i < 0; i++) {
        ms = -sqrt(100.0 - i * i);
        if (t < D0 && !(ms > Q(i)) && fabs(t - D0) >= 1e-4) hline(cx + (int)rnd(k * Q(i)), cy - i, cx + (int)rnd(k * i / tanC), cy - i);
        else hline(cx + (int)rnd(k * ms), cy - i, cx + (int)rnd(k * i / tanC), cy - i);
    }
    if (t < D0) return;
    for (i = 1; i <= 10; i++) {
        int row = cy - i + 1;
        if (!(t > D1) && i > S) return;
        ms = -sqrt(100.0 - i * i);
        if (!(D1 > t) && i > S) hline(cx + (int)rnd(k * ms), row, cx + (int)rnd(-k * ms), row);
        else hline(cx + (int)rnd(k * ms), row, cx + (int)rnd(k * Q(i)), row);
    }
    if (t < D2) return;
    A1 = (int)S; if (A1 >= 0) return;
    for (i = -1; i >= A1; i--) { if (i < S) return; hline(cx + (int)rnd(k * Q(i)), cy - i, cx + (int)rnd(k * sqrt(100.0 - i * i)), cy - i); }
}

/* ---- the key checks: a fake engine that logs what it is told ---- */
static char log_[512];
static int leaves, saves;
static void plog(const char *s) { strcat(log_, s); }
void perf_gesture(int c, int g, int ph) { char b[24]; sprintf(b, "G%d.%d.%d;", c, g, ph); plog(b); }
void perf_turn(int c, int n) { char b[24]; sprintf(b, "T%d.%d;", c, n); plog(b); }
void perf_leave(void) { leaves++; }
int perf_save(int p) { saves += p == 7; return 1; }
static int fails;
static void expect(const char *what, const char *want)
{
    if (strcmp(log_, want)) { printf("FAIL %s: got '%s' want '%s'\n", what, log_, want); fails++; }
    log_[0] = 0;
}
static void polls(int n) { while (n--) perf_poll(); }
static void check(const char *what, int ok) { if (!ok) { printf("FAIL %s\n", what); fails++; } }
static void k(int ev, int a) { perf_key(ev, a); }
static void op(void) { k(34, 1); k(35, 1); }    /* lists: knob 1 opens on release */

static int keys(void)
{
    unsigned short m;
    perf_on = 0; k(160, 1); k(160, 1); op(); check("the ENTER / SETUP choice opens SETUP", perf_on == 2); perf_on = 0; k(160, -5); op();
    check("... and ENTER", perf_on == 1);
    perf_poll(); polls(5);
    k(64, 1); polls(7); k(65, 1); expect("click", "G1.1.0;");
    k(64, 1); polls(1); k(65, 1); expect("bounce under 30 ms", "");
    k(64, 1); polls(30); expect("hold starts at 400 ms", "G1.2.0;"); k(65, 1); expect("hold release", "G1.2.1;");
    k(160, 1); polls(3); k(34, 1); polls(7); k(35, 1); expect("click right after a turn is ignored", "T0.1;");
    polls(10); k(34, 1); polls(7); k(35, 1); expect("click 150 ms after a turn counts", "G0.1.0;");
    k(64, 1); k(161, 1); polls(7); k(65, 1); expect("one detent while pushed is a wobble", "G1.1.0;");
    k(64, 1); k(161, 2); polls(7); k(65, 1); expect("two detents cancel the press", "T1.2;");
    polls(12); k(64, 1); polls(30); k(161, -3); k(65, 1); expect("two detents cancel a hold", "G1.2.0;G1.2.1;T1.-3;");
    k(161, 1); k(161, -1); expect("turns pass", "T1.1;T1.-1;");
    k(32, 1); polls(7); k(33, 1); expect("footswitch press", "G6.1.0;");
    k(32, 1); polls(30); k(33, 1); expect("footswitch hold", "G6.2.0;G6.2.1;");
    k(72, 1); polls(7); k(73, 1); k(70, 1); polls(7); k(71, 1); k(74, 1); polls(30); k(75, 1);
    expect("cursor buttons", "G3.1.0;G4.1.0;G5.2.0;G5.2.1;");
    k(68, 1); k(69, 1); check("cursor up leaves on release", leaves == 1);
    /* SETUP */
    leaves = 0;
    perf_on = 2; perf_patch.cycle = 4; perf_patch.target[1] = T_NONE; perf_patch.move[1][M_PRESS_F] = MV_UNUSED;
    k(160, 0); check("setup starts on the top list", pu_scr == 0);
    k(162, 1); check("knob 3 turn changes the cycle", perf_patch.cycle == 8);
    k(160, 3); check("knob 1 scrolls", pu_pos[0] == 3);
    op(); check("knob 3 press opens a control", pu_scr == 2 && pu_ctl == 1);
    op(); check("TARGET opens the module list", pu_scr == 3);
    k(160, 2); op(); check("a module opens its parameters", pu_scr == 4 && pu_mod == 2);
    k(160, 2); op(); check("a parameter is the target", pu_scr == 2 && perf_patch.target[1] == 14 + 10 * 1 + 2);
    k(160, 2); op(); check("a gesture row opens its moves", pu_scr == 5 && pu_ges == 1);
    k(160, 1); op(); check("a move opens its knob page", pu_scr == 6 && pu_mv == M_PRESS_F);
    k(160, 1); m = perf_patch.move[1][M_PRESS_F]; check("knob 1 edits Value (unused -> 0)", MV_VALUE(m) == 0 && MV_NEXT(m) == NX_NOW);
    k(161, 2); k(162, 3); m = perf_patch.move[1][M_PRESS_F]; check("knobs 2 and 3 edit Next and Lag", MV_NEXT(m) == 2 && MV_LAG(m) == 3);
    k(160, -1); m = perf_patch.move[1][M_PRESS_F]; check("Value back to -", MV_NEXT(m) == NX_UNUSED);
    k(65, 1); check("knob 2 goes back", pu_scr == 5);
    k(65, 1); k(65, 1); check("back to the top list", pu_scr == 0);
    k(65, 1); check("back from the top list opens the Perform menu, no save", perf_on == 0 && pu_scr == 7 && pu_pos[7] == 1 && leaves == 0 && saves == 0);
    k(65, 1); check("EXIT on the Perform menu goes to MENU on PERFORM MODE", host_screen == 2 && leaves == 0);
    perf_on = 2; k(160, 0);
    k(68, 1); k(69, 1); check("cursor up in SETUP does nothing", leaves == 0);
    pu_scr = 2; pu_ctl = 1; pu_ev = -1; pu_pos[2] = 1; perf_patch.target[1] = T_FTSW + 2;
    op(); check("a Footsw target opens its moves", pu_scr == 5);
    return fails;
}

int main(int argc, char **argv)
{
    int i;
    FILE *f;
    char path[512];
    host_fx[3][1] = 497;
    for (i = 0; i < 3; i++) host_fx[i][1] = 1;
    if (argc > 1 && !strcmp(argv[1], "keys")) { i = keys(); puts(i ? "keys: FAILED" : "keys: all passed"); return i != 0; }
    for (i = 0; i < NSTATES; i++) {
        memset(&perf_patch, 0, sizeof perf_patch);
        memset(host_val, 0, sizeof host_val);
        memset(host_svc, 0, sizeof host_svc);
        memset(host_lcd, 0, sizeof host_lcd);
        memset(&perf_grid, 0, sizeof perf_grid);
        memset(host_pend, 0xFF, sizeof host_pend);
        pu_scr = 0; pu_ev = -1; pu_ges = 1; pu_mv = 1; pu_ctl = 0; pu_mod = 1; memset(pu_pos, 0, sizeof pu_pos);
        perf_on = 1;
        state(i);
        perf_draw();
        sprintf(path, "%s/%s.fb", argv[1], state_name(i));
        f = fopen(path, "wb");
        fwrite(host_lcd, 1, 1024, f);
        fclose(f);
    }
    return 0;
}
'''

# ---- the mockup side -----------------------------------------------------------------------------
NODE_JS = r'''
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
let src = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
// the C names an effect's parameters Knob1 ... (their real names are not read yet): rename the mockup's FX example to match
const knobs = n => Array.from({ length: n }, (_, i) => `kn("Knob${i + 1}", 127, 0)`).join(", ");
src = src.replace(/  \{ id: "FX1".*\n/, `  { id: "FX1", name: "DELAY", p: [onoff(), ${knobs(9)}] },\n`)
  .replace(/  \{ id: "FX2".*\n/, `  { id: "FX2", name: "TREMOLO", p: [onoff(), ${knobs(9)}] },\n`)
  .replace(/  \{ id: "FX3".*\n/, `  { id: "FX3", name: "HALL", p: [onoff(), ${knobs(9)}] },\n`)
  .replace(/  \{ id: "FX4".*\n/, `  { id: "FX4", name: "LOOPER", p: [onoff(), { n: "Ftsw", t: "trig" }, ${knobs(9)}] },\n`);
const specs = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const body = `
let FAKE = 1000000;
const performance = { now: () => FAKE };
const stub = new Proxy(function () {}, { get: (t, k) => k === "getContext" ? () => stub : k === "querySelectorAll" ? () => [] : stub, apply: () => stub, set: () => true });
const document = { getElementById: () => stub, querySelectorAll: () => [], addEventListener() {} };
const requestAnimationFrame = () => {};
${src}
const GN = ["turn", "press", "hold"], MV = ["F", "A", "F", "A", "R", "F"], KEYS = [["turn", "F"], ["press", "A"], ["press", "F"], ["hold", "A"], ["hold", "R"], ["hold", "F"]];
const out = {};
for (const sp of SPECS) {
  FAKE = 1000000; reset(); clock = sp.now >= 0;
  S.cyc = CYC.indexOf(sp.cyc);
  FAKE = 1000000 + Math.max(0, sp.now);
  CTL.forEach((c, i) => {
    c.tgt = sp.targets[i];
    KEYS.forEach(([g, k], j) => {
      const e = sp.moves[i][j];
      if (c[g]) c[g][k] = e ? { v: Math.floor((e[0] * par(c.tgt).max + 63) / 127), w: e[1], l: e[2] } : { v: -1, w: 0, l: 0 };
    });
  });
  for (const t in sp.values) V[t] = Math.floor((sp.values[t] * par(t).max + 63) / 127);
  P = [];
  for (const i in sp.pend) if (+i < 6) P.push({ c: CTL[i], tgt: CTL[i].tgt, v: 0, lag: 0, at: now() + sp.pend[i] * 62.5, then: null });
  L = { st: "empty", at: 0, end: 0, start: 0, len: 0, pstart: 0, pass: 0 };
  if (sp.arm != null) { L.st = "arm"; L.at = now() + sp.arm; }
  if (sp.status.startsWith("REC")) { L.st = "rec"; L.start = now() - 1.4 * BAR; }
  S.tab = sp.screen === "play" ? "play" : "setup";
  S.scr = { top: "list", ctl: "ctl", ges: "ges", move: "move", pmod: "pmod", ppar: "ppar" }[sp.screen];
  S.row = sp.pos; S.crow = sp.pos; S.mrow = sp.pos; S.pm = sp.screen === "pmod" ? sp.pos : sp.pm; S.pp = sp.pp; S.ctl = sp.ctl; S.ev = -1;
  S.ges = GN[sp.ges]; S.mv = MV[sp.mv];
  lt = 0;
  fb.fill(0);
  S.tab === "play" ? drawPlay() : drawSetup();
  out[sp.name] = Buffer.from(fb).toString("base64");
}
return out;`;
const res = new Function("SPECS", body)(specs);
fs.writeFileSync(process.argv[4], JSON.stringify(res));
'''


def find_cc():
    for name in ("gcc", "clang", "cc"):
        if shutil.which(name):
            return [shutil.which(name)]
    for p in EXTRA:
        if Path(p).exists():
            return [p]
    if subprocess.run([sys.executable, "-m", "ziglang", "version"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "ziglang", "cc"]
    return None


def hexbytes(name):
    h = re.search(r'const ' + name + r'\s*=\s*"([0-9a-f]+)"', MOCKUP.read_text(encoding="utf-8")).group(1)
    return ",".join(str(int(h[i:i + 2], 16)) for i in range(0, len(h), 2))


def gen_c(sts):
    """host_data.h: the mockup's bitmaps and the state setters."""
    o = [f"static const unsigned char host_{n}[] = {{{hexbytes(n)}}};" for n in ("F7", "TOG0", "TOG1", "FAD", "KNOB")]
    o.append(f"#define NSTATES {len(sts)}")
    o.append("static void state(int n)\n{\n    switch (n) {")
    for i, (_, s) in enumerate(sts):
        o.append(f"    case {i}:")
        o.append(f"        perf_patch.cycle = {s['cyc']};")
        for c, t in enumerate(s["targets"]):
            o.append(f"        perf_patch.target[{c}] = {cc(t)};")
            for m in range(6):
                e = s["moves"][c][m]
                o.append(f"        perf_patch.move[{c}][{m}] = " + (f"MV({e[0]}, {e[1]}, {e[2]});" if e else "MV_UNUSED;"))
        for t, v in s["values"].items():
            o.append(f"        host_val[{cc(t)}] = {v};")
        for c, ms in s["pend"].items():
            o.append(f"        host_pend[{c}] = {ms};")
        if s["now"] >= 0:
            now = s["now"]
            o.append(f"        perf_grid.beat = {now // 500}; perf_grid.frac = {(now % 500) * 65536 // 500}; perf_grid.running = 1; perf_grid.bpm_x10 = 1200;")
        o.append(f"        host_svc[0] = 0x5A4C5301; host_svc[8] = 1; host_svc[10] = 3; host_fx[3][0] = 1; perf_patch.loop_on = 1;")
        st = s["status"].ljust(8).encode()
        o.append(f"        host_svc[17] = {int.from_bytes(st[:4], 'little')}; host_svc[18] = {int.from_bytes(st[4:], 'little')};")
        scr = dict(play=None, menu=7, top=0, ctl=2, ges=5, move=6, pmod=3, ppar=4)[s["screen"]]
        if scr is not None:
            o.append(f"        perf_on = {0 if scr == 7 else 2}; pu_scr = {scr}; pu_pos[{scr}] = {s['pos']}; pu_ctl = {s['ctl']}; pu_ges = {s['ges']}; pu_mv = {s['mv']}; pu_mod = {s['pm']};")
            if scr == 4:
                o.append(f"        pu_pos[4] = {s['pp']};")
        o.append("        break;")
    o.append("    }\n}")
    o.append("static const char *state_name(int n)\n{\n    static const char *const N[] = {" + ",".join(f'"{n}"' for n, _ in sts) + "};\n    return N[n];\n}")
    return "\n".join(o) + "\n"


def render(fb, scale=4):
    """fb: page-format bytes (1024)."""
    img = Image.new("RGB", (128, 64))
    img.putdata([INK if fb[(y >> 3) * 128 + x] >> (y & 7) & 1 else BG for y in range(64) for x in range(128)])
    return img.resize((128 * scale, 64 * scale), Image.NEAREST)


def run(outdir):
    cc_ = find_cc()
    if cc_ is None:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / "host"
    work.mkdir(exist_ok=True)
    sts = states()
    (work / "perf_host.h").write_text(HOST_H, newline="\n")
    (work / "host_data.h").write_text(gen_c(sts), newline="\n")
    (work / "host.c").write_text(HOST_C, newline="\n")
    exe = work / "perform_host.exe"
    cmd = cc_ + ["-std=gnu99", "-Wall", "-O1", "-DPERF_HOST", f"-I{work}", f"-I{PERF}", str(work / "host.c"), str(PERF / "perform_draw.c"),
                 str(PERF / "perform_keys.c"), "-lm", "-o", str(exe)]
    subprocess.run(cmd, check=True)
    subprocess.run([str(exe), str(outdir)], check=True)
    keys = subprocess.run([str(exe), "keys"], capture_output=True, text=True)
    print(keys.stdout.strip())
    mock = {}
    if shutil.which("node"):
        specs = [dict(s, name=n) for n, s in sts]
        (work / "mock.js").write_text(NODE_JS, encoding="utf-8")
        (work / "specs.json").write_text(json.dumps(specs))
        subprocess.run(["node", str(work / "mock.js"), str(MOCKUP), str(work / "specs.json"), str(work / "mock.json")], check=True)
        mock = json.loads((work / "mock.json").read_text())
    pngs = []
    for n, _ in sts:
        fb = (outdir / f"{n}.fb").read_bytes()
        render(fb).save(outdir / f"{n}.png")
        pngs.append(outdir / f"{n}.png")
        if n in mock:
            px = base64.b64decode(mock[n])
            rows = [px[y * 128:(y + 1) * 128] for y in range(64)]
            mfb = bytes(sum(rows[(p << 3) + r][x] << r for r in range(8)) for p in range(8) for x in range(128))
            render(mfb).save(outdir / f"{n}_mockup.png")
            diff = sum(bin(a ^ b).count("1") for a, b in zip(fb, mfb))
            print(f"{n}: {diff} pixels differ from the mockup")
    return pngs, keys.returncode


if __name__ == "__main__":
    r = run(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/out/perform-preview")
    if r is None:
        sys.exit("no host C compiler found (gcc, clang, or `pip install ziglang`)")
    print("\n".join(map(str, r[0])))
    sys.exit(2 if False else r[1])
