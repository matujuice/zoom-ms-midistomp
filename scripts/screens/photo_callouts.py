"""Pedal photos for the guide, labelled in the LCD look: tags in the firmware's FONT7 (asm/common/draw.h), drawn in
chunky pixels with the screen shots' ink, and stepped pixel leader lines to what they name.

Usage: py scripts/screens/photo_callouts.py [outdir]   (default docs/img; sources in scripts/screens/photos)"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INK, PAPER = (44, 44, 130), (220, 222, 226)       # make_screens.py's ink and LCD glass
S = 3                                             # photo px per LCD pixel

F7 = [int(v) for v in re.search(r"F7\[\d+\] = \{(.*?)\};", (ROOT / "asm/common/draw.h").read_text(), re.S)[1].split(",") if v.strip()]
ARROWS = {"^": [0x20, 0x30, 0x38, 0x3C, 0x38, 0x30, 0x20], "v": [0x04, 0x0C, 0x1C, 0x3C, 0x1C, 0x0C, 0x04],
          "<": [0x08, 0x1C, 0x3E, 0x7F, 0, 0, 0], ">": [0x7F, 0x3E, 0x1C, 0x08, 0, 0, 0]}


def glyph(ch):
    return ARROWS.get(ch) or F7[7 * (ord(ch) - 32): 7 * (ord(ch) - 32) + 7]


def tag(d, text, x, y, s=S):
    """An inverted LCD tag, top-left (x, y): ink box, glass-coloured FONT7 text. Returns its box."""
    w, h = (7 * len(text) + 3) * s, 11 * s
    d.rectangle((x - s, y - s, x + w + s - 1, y + h + s - 1), fill=PAPER)       # 1 px glass rim, reads on any photo
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=INK)
    for i, ch in enumerate(text):
        for c, col in enumerate(glyph(ch)):
            for r in range(8):
                if col >> r & 1:
                    X, Y = x + (2 + 7 * i + c) * s, y + (2 + r) * s
                    d.rectangle((X, Y, X + s - 1, Y + s - 1), fill=PAPER)
    return x, y, x + w - 1, y + h - 1


def lead(d, box, tx, ty, s=S):
    """A stepped pixel line from the tag's nearest edge to (tx, ty), ending in a hollow 5 px square."""
    x0, y0, x1, y1 = box
    sx = min(max(tx, x0), x1)
    sy = min(max(ty, y0), y1)
    if x0 <= tx <= x1:
        sy = y1 + s if ty > y1 else y0 - s
    elif y0 <= ty <= y1:
        sx = x1 + s if tx > x1 else x0 - s
    a, b = sx // s, sy // s
    ex, ey = tx // s, ty // s
    n = max(abs(ex - a), abs(ey - b), 1)
    for i in range(n - 1):                        # stop short of the target square
        X, Y = round(a + (ex - a) * i / n) * s, round(b + (ey - b) * i / n) * s
        d.rectangle((X - s, Y - s, X + s - 1, Y + s - 1), fill=PAPER)
        d.rectangle((X, Y, X + s - 1, Y + s - 1), fill=INK)
    X, Y = ex * s, ey * s
    d.rectangle((X - 3 * s, Y - 3 * s, X + 3 * s - 1, Y + 3 * s - 1), outline=PAPER, width=s)
    d.rectangle((X - 2 * s, Y - 2 * s, X + 2 * s - 1, Y + 2 * s - 1), outline=INK, width=s)


# photo: crop box or None, canvas padding (l, t, r, b), [(text, tag x, tag y, target x, target y or None)], in photo px
PHOTOS = {
    "ms70cdr-front.jpg": (None, (150, 0, 150, 0), [
        ("OUT", -140, 175, 15, 185), ("IN", 640, 175, 590, 185),
        ("KNOB 1", 70, 495, None, None), ("KNOB 2", 238, 495, None, None), ("KNOB 3", 405, 495, None, None),
        ("SOFTKEYS", -140, 255, 175, 277),
        ("^", 288, 656, None, None), ("<", 207, 732, None, None), (">", 375, 732, None, None), ("v", 288, 812, None, None),
        ("CURSOR KEYS", -140, 900, 230, 800),
        ("FOOTSWITCH", 520, 900, 330, 780),
    ]),
    "ms70cdr-usb.jpg": ((250, 240, 600, 480), (0, 0, 0, 60), [
        ("MINI-USB", 262, 495, 402, 398), ("POWER", 470, 495, 516, 353),
    ]),
    "ms70cdr-stereo.jpg": (None, (0, 0, 0, 0), [
        ("IN L/R", 560, 30, 470, 120), ("OUT L/R", 10, 330, 210, 405),
    ]),
    "ms70cdr-foot.jpg": ((380, 0, 960, 549), (0, 0, 0, 0), [
        ("LED", 470, 430, 684, 357), ("FOOTSWITCH", 650, 20, 880, 230),
    ]),
}


def make(name, crop, pad, calls):
    im = Image.open(HERE / "photos" / name).convert("RGB")
    if crop:
        im = im.crop(crop)
    ox, oy = (crop[0], crop[1]) if crop else (0, 0)
    l, t, r, b = pad
    out = Image.new("RGB", (im.width + l + r, im.height + t + b), (255, 255, 255))
    out.paste(im, (l, t))
    d = ImageDraw.Draw(out)
    boxes = [(tag(d, text, x - ox + l, y - oy + t), tx, ty) for text, x, y, tx, ty in calls]
    for box, tx, ty in boxes:
        if tx is not None:
            lead(d, box, tx - ox + l, ty - oy + t)
    for (text, x, y, *_), (box, *_) in zip(calls, boxes):   # tags on top of every leader
        tag(d, text, box[0], box[1])
    return out


def main(out):
    for name, (crop, pad, calls) in PHOTOS.items():
        make(name, crop, pad, calls).save(out / name, quality=90)
        print(out / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/img")
