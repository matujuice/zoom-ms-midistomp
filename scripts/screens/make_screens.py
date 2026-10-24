"""README and user-guide screen shots, all drawn by the firmware's own draw code on the host, then shown in the
pedal LCD look (tall 6x9 pixels, 1 px grid, near-flat blue-violet ink, glass margin, dark bezel).

Usage: py scripts/screens/make_screens.py [outdir]   (default docs/img)
Needs a host C compiler (gcc, clang or `pip install ziglang`); node is optional for PERFORM. The stock-UI shots
(boot, MENU, SETTINGS, MIDI, tempo, HOLD FOR) also need Zoom's updater and TI CGT, see fw_shot.py."""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from chain_draw_preview import find_cc  # noqa: E402
import perform_draw_preview  # noqa: E402
sys.path.insert(0, str(HERE))
import fw_shot  # noqa: E402

W, H = 128, 64
CW, CH, M, B = 6, 9, 18, 14                      # cell w/h (the LCD's pixels are ~1.45x taller than wide), margin, bezel
BG, OFF, GAP = (220, 222, 226), (209, 212, 218), (226, 228, 231)
STOPS = [(0, (40, 48, 128)), (0.5, (44, 44, 130)), (1, (52, 40, 128))]   # almost flat, a touch bluer left, more violet right

# output png: (source dir key, .fb name, framebuffer format)
SHOTS = {
    "mixer-chain.png": ("chain", "rm_a0", "rows"),
    "mixer-chain-bus-b.png": ("chain", "rm_a1", "rows"),
    "mixer-chain-route.png": ("chain", "rm_route", "rows"),
    "mixer-chain-mix.png": ("chain", "rm_mix", "rows"),
    "perform.png": ("perform", "play_recording", "pages"),
    "perform-menu.png": ("perform", "perform_menu", "pages"),
    "perform-idle.png": ("perform", "play_idle", "pages"),
    "perform-no-clock.png": ("perform", "play_no_clock", "pages"),
    "perform-rec-in.png": ("perform", "play_rec_in_a", "pages"),
    "perform-knob-touched.png": ("perform", "play_rec_in_b", "pages"),
    "perform-setup.png": ("perform", "setup_top", "pages"),
    "perform-setup-knob.png": ("perform", "setup_control", "pages"),
    "perform-setup-gesture.png": ("perform", "setup_gestures", "pages"),
    "perform-setup-target.png": ("perform", "setup_module", "pages"),
    "perform-setup-move.png": ("perform", "setup_move", "pages"),
    "perform-setup-move-lag.png": ("perform", "setup_move_lag", "pages"),
    "perform-setup-param.png": ("perform", "setup_param", "pages"),
    "master.png": ("master", "master_spectrum", "ascii"),
    "master-scope.png": ("master", "master_scope", "ascii"),
    "master-stereo.png": ("master", "master_stereo", "ascii"),
    "master-loudness.png": ("master", "master_loudness", "ascii"),
    "master-in-meter.png": ("master", "master_input", "ascii"),
    "master-out-meter.png": ("master", "master_meters", "ascii"),
    "kaleido.png": ("master", "master_kaleido", "ascii"),
    "boot-screen.png": ("fw", "boot", "ascii"),
    "menu.png": ("fw", "menu", "ascii"),
    "settings.png": ("fw", "settings", "ascii"),
    "midi-menu.png": ("fw", "midi_menu", "ascii"),
    "tempo-turn-tap.png": ("fw", "tempo_turn_tap", "ascii"),
    "tempo-midi-clock.png": ("fw", "tempo_clock", "ascii"),
    "hold-for.png": ("fw", "hold_for", "ascii"),
    "menu-2.png": ("fw", "menu_2", "ascii"),
    "settings-2.png": ("fw", "settings_2", "ascii"),
    "settings-3.png": ("fw", "settings_3", "ascii"),
    "midi-menu-2.png": ("fw", "midi_menu_2", "ascii"),
    "system-version.png": ("fw", "system_version", "ascii"),
    "system-load.png": ("fw", "system_load", "ascii"),
    "system-effects.png": ("fw", "system_effects", "ascii"),
    "system-mods.png": ("fw", "system_mods", "ascii"),
    "mixer-in.png": ("fw", "mixer_in", "ascii"),
    "mixer-route.png": ("fw", "mixer_route", "ascii"),
    "mixer-mix-1.png": ("fw", "mixer_mix_1", "ascii"),
    "mixer-mix-2.png": ("fw", "mixer_mix_2", "ascii"),
    "mixer-mix-3.png": ("fw", "mixer_mix_3", "ascii"),
    "mixer-out.png": ("fw", "mixer_out", "ascii"),
}


def pixels(b, fmt):
    if fmt == "ascii":
        return [[b[y * W + x] == 49 for x in range(W)] for y in range(H)]
    if fmt == "rows":
        return [[b[y * 16 + x // 8] >> (7 - x % 8) & 1 for x in range(W)] for y in range(H)]
    return [[b[(y >> 3) * W + x] >> (y & 7) & 1 for x in range(W)] for y in range(H)]


def ink(t):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return tuple(round(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))


def lcd(p, cw=CW, ch=CH, mx=M, my=M):
    """p: rows of pixels, True ink, False off, None bare glass (between KALEIDO grid tiles)."""
    w, h = len(p[0]), len(p)
    sw, sh = w * cw + 2 * mx, h * ch + 2 * my
    im = Image.new("RGB", (sw + 2 * B, sh + 2 * B), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), 16, fill=(24, 24, 27))
    d.rounded_rectangle((B, B, B + sw - 1, B + sh - 1), 4, fill=BG)
    for y in range(h):
        for x in range(w):
            if p[y][x] is None:
                continue
            X, Y = B + mx + x * cw, B + my + y * ch
            d.rectangle((X, Y, X + cw - 1, Y + ch - 1), fill=GAP)
            d.rectangle((X, Y, X + cw - 2, Y + ch - 2), fill=ink(x / (w - 1)) if p[y][x] else OFF)
    return im


def kaleido_grid(fbs, cols=5, rows=6, g=6, cw=3, ch=4):
    """The README's closing cover: 30 KALEIDO frames on one LCD, 5:4."""
    gw, gh = cols * W + (cols - 1) * g, rows * H + (rows - 1) * g
    p = [[None] * gw for _ in range(gh)]
    for i, fb in enumerate(fbs[:cols * rows]):
        ox, oy = i % cols * (W + g), i // cols * (H + g)
        for y, row in enumerate(pixels(fb, "ascii")):
            p[oy + y][ox:ox + W] = row
    mx = my = 4 * M // 3
    tw, th = gw * cw + 2 * (mx + B), gh * ch + 2 * (my + B)     # pad the shorter side's glass so the whole image is 5:4
    k = -(-max(tw * 4, th * 5) // 20)               # 5k x 4k fits both; even k keeps both paddings even
    k += k & 1
    mx, my = mx + (5 * k - tw) // 2, my + (4 * k - th) // 2
    return lcd(p, cw, ch, mx, my)


def build(cc, srcs, incs, exe, run_dir):
    subprocess.run(cc + ["-std=gnu99", "-O1", "-w", *("-I" + str(i) for i in incs), *map(str, srcs), "-o", str(exe)], check=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(exe), str(run_dir)], check=True)


def main(out):
    cc = find_cc()
    if cc is None:
        sys.exit("no host C compiler found (gcc, clang, or `pip install ziglang`)")
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        dirs = {k: t / k for k in ("chain", "master", "perform", "fw")}
        build(cc, [ROOT / "asm/mixer/chain_draw.c", HERE / "chain_shot.c"], [ROOT / "asm/mixer"], t / "chain.exe", dirs["chain"])
        build(cc, [HERE / "master_shot.c"], [ROOT / "tests/master_host", ROOT / "asm/master", ROOT / "asm/mixer"],
              t / "master.exe", dirs["master"])
        subprocess.run([str(t / "master.exe"), str(dirs["master"]), "grid"], check=True)
        perform_draw_preview.run(dirs["perform"])
        if fw_shot.available():
            fw_shot.run(t / "fw")
        else:
            print(f"skipping stock-UI shots: needs {fw_shot.UPDATER} and TI CGT at {fw_shot.CGT}")
        out.mkdir(parents=True, exist_ok=True)
        for png, (k, name, fmt) in SHOTS.items():
            if not (dirs[k] / f"{name}.fb").exists():
                continue
            lcd(pixels((dirs[k] / f"{name}.fb").read_bytes(), fmt)).save(out / png)
            print(out / png)
        order = [2, 17, 9, 25, 5, 21, 0, 28, 13, 7, 16, 3, 19, 11, 24, 6, 27, 1, 22, 15, 29, 8, 14, 20, 4, 18, 26, 10, 23, 12]
        kaleido_grid([(dirs["master"] / f"master_grid{i:02d}.fb").read_bytes() for i in order]).save(out / "kaleido-grid.png")
        print(out / "kaleido-grid.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/img")
