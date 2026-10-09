# Draws the pedal screens for docs/img/ with the OS's own 6x8 font (0xC00E9188)
# and the list layout of the stock SETTINGS draw (see asm/midi_settings/settings.S).
# Usage: python3 scripts/guide_screens.py 129_main_OS.bin docs/img
# (129_main_OS.bin from `zoomms updater-parts <stock MS-50G 3.10 updater> --out DIR`)
import sys
import yaml
from zoomms import ais
from PIL import Image, ImageDraw
img = ais.parse(open(sys.argv[1], 'rb').read())
OUT = sys.argv[2]
FONT = img.read(0xC00E9188, 6 * 128)
def cstr(a):
    b = img.read(a, 40); return b[:b.index(0)].decode('latin-1')
W, H = 128, 64
class Scr:
    def __init__(s): s.p = [[0] * W for _ in range(H)]
    def set(s, x, y, v=1):
        if 0 <= x < W and 0 <= y < H: s.p[y][x] = v
    def text(s, t, x, y, inv=False, bold=False):
        for c in t:
            col = FONT[(ord(c) & 127) * 6:(ord(c) & 127) * 6 + 6]
            for i, b in enumerate(col):
                for r in range(8):
                    if b >> r & 1:
                        s.set(x + i, y + r, 0 if inv else 1)
                        if bold: s.set(x + i + 1, y + r, 0 if inv else 1)
            x += 6 + (1 if bold else 0)
        return x
    def big(s, t, x, y, inv=False):  # the 6x8 font at 2x, for the tempo box
        for c in t:
            col = FONT[(ord(c) & 127) * 6:(ord(c) & 127) * 6 + 6]
            for i, b in enumerate(col):
                for r in range(8):
                    if b >> r & 1: s.box(x + 2 * i, y + 2 * r, x + 2 * i + 1, y + 2 * r + 1, 0 if inv else 1)
            x += 12
    def box(s, x0, y0, x1, y1, v=1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1): s.set(x, y, v)
    def icon(s, cols, x, y, v=1):
        for i, b in enumerate(cols):
            for r in range(7):
                if b >> r & 1: s.set(x + i, y + r, v)
    def png(s, path, sc=4):
        fg = (28, 36, 58); bg = (196, 214, 226)
        im = Image.new('RGB', (W * sc + 32, H * sc + 32), (30, 30, 32)); d = ImageDraw.Draw(im)
        d.rectangle([16, 16, 16 + W * sc - 1, 16 + H * sc - 1], fill=bg)
        for y in range(H):
            for x in range(W):
                if s.p[y][x]: d.rectangle([16 + x * sc, 16 + y * sc, 16 + x * sc + sc - 1, 16 + y * sc + sc - 1], fill=fg)
        im.save(path)
def title(s, t):
    s.box(0, 0, W - 1, 9)
    w = len(t) * 7
    s.text(t, max(1, (W - w) // 2), 1, inv=True, bold=True)
def tri(s, x, y, up):
    for r in range(3):
        for i in range(-r, r + 1): s.set(x + i, y + (r if up else 2 - r))
def softkeys(s, labels, arrows=True):
    for k, l in enumerate(labels):
        x0 = k * 43; x1 = x0 + 41
        s.box(x0, 54, x1, 63)
        if l: s.text(l, x0 + (42 - len(l) * 6) // 2 + 1, 55, inv=True)
    if arrows: tri(s, 16, 48, True); tri(s, 24, 48, False)
def lst(t, names, rows_hi, top=0, icons=None, left='ENTER'):
    s = Scr(); title(s, t)
    bar = len(names) > 4
    for r in range(4):
        i = top + r
        if i >= len(names): break
        y = 12 + 9 * r
        if i == top + rows_hi: s.box(0, y - 1, 119 if bar else W - 1, y + 7)
        if icons: s.icon(icons(i), 1, y, 0 if i == top + rows_hi else 1)
        s.text(names[i], 12 if icons else 1, y, inv=(i == top + rows_hi))
    if bar:
        tri(s, 124, 11, True); tri(s, 124, 45, False)
        s.box(122, 15, 126, 43, 0)
        for y in range(15, 44): s.set(122, y); s.set(126, y)
        n = len(names); h = max(4, 29 * 4 // n); y0 = 15 + (29 - h) * top // max(1, n - 4)
        s.box(122, y0, 126, y0 + h - 1)
    softkeys(s, [left, 'EXIT', ''])
    return s
menu = [cstr(0xC00E9484), cstr(0xC00E9497), cstr(0xC00E94A4), 'MIDI', 'V1.0']
lst(cstr(0xC00E958C), menu, 3).png(OUT + '/menu.png')
midi = ['CLOCK RECEIVE', 'TRANSPORT RECEIVE', 'PROG CH RECEIVE', 'PROG CH START NO.', 'CC RECEIVE', 'MIDI CHANNEL']
micon = [0x1c, 0x22, 0x55, 0x41, 0x55, 0x22, 0x1c]
lst('MIDI', midi, 0, icons=lambda i: micon).png(OUT + '/midi-menu.png')
lst('HOLD FOR', ['TUNER', 'TEMPO', 'MOMENTARY'], 2, left='').png(OUT + '/hold-for.png')
setn = ['HOLD FOR'] + [cstr(a) for a in (0xC00E94C8, 0xC00E94DA, 0xC00E94EB, 0xC00E94F5, 0xC00E9502, 0xC00E9510)] + ['TEMPO LOCK']
sic = bytes.fromhex('1c3e4f417b361c 00001f601f0000 1c22404f40221c 70444c5f4c4470 007e7f7f7f7e00 7f415d5d5d417f 1c2271797d3e1c 787e7949797e78'.replace(' ', ''))
lst(cstr(0xC00E94A4), setn, 3, top=4, icons=lambda i: sic[i * 7:i * 7 + 7]).png(OUT + '/settings.png')
logo = bytes.fromhex(yaml.safe_load(open('patches/boot-logo.yaml'))['bin133'][0]['data'])
b = Scr()
for y in range(H):
    for x in range(W): b.p[y][x] = logo[(y // 8) * W + x] >> (y % 8) & 1
b.text('v1.0', (W - 24) // 2, 50)  # the OS prints the version here
b.png(OUT + '/boot-screen.png')
# banner: the boot screen on an MS-50G grey panel
sc = 6; fg = (28, 36, 58); bgc = (196, 214, 226)
ban = Image.new('RGB', (1200, 480), (88, 91, 96)); d = ImageDraw.Draw(ban)
x0, y0 = (1200 - W * sc) // 2, (480 - H * sc) // 2
d.rounded_rectangle([x0 - 20, y0 - 20, x0 + W * sc + 19, y0 + H * sc + 19], radius=16, fill=(32, 33, 36))
d.rectangle([x0, y0, x0 + W * sc - 1, y0 + H * sc - 1], fill=bgc)
for y in range(H):
    for x in range(W):
        if b.p[y][x]: d.rectangle([x0 + x * sc, y0 + y * sc, x0 + x * sc + sc - 1, y0 + y * sc + sc - 1], fill=fg)
ban.save(OUT + '/banner.png')
# tempo screen: the stock tempo box with our TURN OR TAP / MIDI CLOCK line
for name, line in (('tempo-turn-tap', 'TURN OR TAP'), ('tempo-midi-clock', 'MIDI CLOCK')):
    t = Scr()
    t.box(4, 14, 123, 47); t.box(5, 15, 122, 46, 0)
    t.box(8, 19, 70, 36); t.big('TEMPO', 10, 20, inv=True); t.big('122', 78, 20)
    t.text(line, (W - 6 * len(line)) // 2, 38)
    softkeys(t, ['TEMPO', 'EXIT', 'PAGE'], arrows=False)
    t.png(OUT + '/' + name + '.png')
