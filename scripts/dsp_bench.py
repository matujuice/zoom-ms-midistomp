"""DSP cost bench for MIDISTOMP pedals (MS-70CDR, MS-60B) over USB MIDI.

Loads chains into the pedal's edit buffer with the stock Zoom SysEx (28 patch dump, 31 parameter
edit in editor mode, docs/dev/os-reverse-engineering.md), reads the SYSTEM timing numbers with the
MIDISTOMP SysEx 06 (asm/diag/diag.c) after each change, and writes one CSV row per point. The
patch stored in flash is never written; the edit buffer is put back at the end.

    py scripts/dsp_bench.py sweep [--steps 3] [--only Washout,LOUDER] [--csv out.csv]
    py scripts/dsp_bench.py chain Washout LOUDER GRDLOOP      # one chain, as loaded
    py scripts/dsp_bench.py watch --seconds 60                 # the patch playing (PERFORM...)
    add --dry-run to print the SysEx it would send, without a pedal.

sweep: each pack effect alone with its defaults, on and off, then each knob from min to max in
--steps steps; at the end it asks for a full patch with PERFORM running and logs it (watch).
Numbers are cycles of an 8-frame block; 1% = PERIOD / 100 (54,422 at 300 MHz, 65,306 at 360).
Needs mido and python-rtmidi. Close the editor and Effect Manager first.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zoomms.midi import IDENTITY_REQUEST, find_port, parse_identity_reply  # noqa: E402

PACK = next((p / "zoom-ms-zdl-effects-pack" for p in ROOT.parents if (p / "zoom-ms-zdl-effects-pack").is_dir()),
            ROOT.parent / "zoom-ms-zdl-effects-pack")  # sibling of the repo, also from a worktree
BENCH = [0x7D, 0x4D, 0x53, 0x54, 0x06]          # F0 7D "MST" 06 nonce F7 -> 47
WORDS = ["per", "ch", "chmax", "own"] + ["cyc%d" % i for i in range(7)] + ["cmax%d" % i for i in range(7)] \
    + ["late", "win", "midi", "late_total", "period"] + ["dsp%d" % i for i in range(1, 7)]
# effect parameters 1-9: [first bit, width] in a slot's 144-bit block (editor/patch.js PARAM_BITS)
PARAM_BITS = [(29, 13), (42, 13), (55, 13), (68, 8), (76, 8), (84, 8), (92, 8), (100, 28), (128, 8)]


def unpack7(d):
    out = []
    for i in range(0, len(d), 8):
        out += [d[i + j] | (0x80 if d[i] & (0x40 >> (j - 1)) else 0) for j in range(1, min(8, len(d) - i))]
    return out


def pack7(b):
    out = []
    for i in range(0, len(b), 7):
        g = b[i:i + 7]
        out += [sum(0x40 >> j for j, x in enumerate(g) if x & 0x80)] + [x & 0x7F for x in g]
    return out


def parse_bench(data):
    """data: a SysEx body without F0/F7. The 29 numbers of reply 47 by name, or None."""
    if len(data) < 6 or data[:4] != BENCH[:4] or data[4] != 0x47:
        return None
    b = unpack7(list(data[6:]))
    if len(b) != 4 * len(WORDS):
        return None
    return {k: int.from_bytes(bytes(b[4 * i:4 * i + 4]), "little") for i, k in enumerate(WORDS)}


def set_bits(rec, x, width, v):
    for b in range(width):
        i = x + b
        rec[i >> 3] = rec[i >> 3] & ~(1 << (i & 7)) | (v >> b & 1) << (i & 7)


def build_chain(rec, effects):
    """rec (122 bytes) with effects [(manifest, on)] in slots 0.., defaults, the rest empty.
    MIDISTOMP routing byte 17 cleared: the stock serial layout."""
    rec = list(rec)
    for s in range(6):
        for j in range(18):
            rec[18 * s + j] = 0
        if s < len(effects):
            m, on = effects[s]
            b = ((m["gid"] << 24 | m["fxid"]) << 1 & 0xFFFFFFFF).to_bytes(4, "little")
            rec[18 * s], rec[18 * s + 1], rec[18 * s + 3] = b[0] & 0xFE | on, b[1] & 7, b[3] & 0x1F  # patch.js
            for p, (x, w) in enumerate(PARAM_BITS):
                if p < len(m["params"]):
                    set_bits(rec, 144 * s + x, w, m["params"][p]["default"])
        else:
            rec[18 * s] = 1                             # empty: on, id 0, as the pedal leaves it
    n = max(1, len(effects))                            # bytes 108-110: DSP-off mask, cursor, COUNT
    t = rec[108] | rec[109] << 8 | rec[110] << 16
    t = t & ~0x1FFF | 5 << 6 | n << 10
    rec[108], rec[109], rec[110] = t & 255, t >> 8 & 255, rec[110] & 0xE0 | t >> 16 & 0x1F
    rec[111:121] = list(b"DSP BENCH ")
    return rec


def load_pack(path):
    ms = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(Path(path).glob("src/custom/*/manifest_pedal.json"))]
    if not ms:
        sys.exit("no pack manifests under %s (pass --pack)" % path)
    return {m["effect_name"].upper(): m for m in ms}


class Pedal:
    def __init__(self, port, dry):
        self.dry, self.dev, self.nonce = dry, 0x61, 0
        if dry:
            return
        import mido
        self.mido = mido
        out = port or find_port(mido.get_output_names())
        inp = port if port in mido.get_input_names() else find_port(mido.get_input_names())
        if not out or not inp:
            sys.exit("no Zoom MIDI port found; pass --port")
        self.out, self.inp = mido.open_output(out), mido.open_input(inp)
        r = self.ask(IDENTITY_REQUEST, lambda d: parse_identity_reply(d))
        if not r:
            sys.exit("no identity reply from %s" % out)
        self.dev = r.family
        print("pedal: model id 0x%02X, version %s" % (self.dev, r.version))

    def send(self, body):
        if self.dry:
            print("F0 " + " ".join("%02X" % b for b in body) + " F7")
            return
        self.out.send(self.mido.Message("sysex", data=body))

    def ask(self, body, parse, timeout=2.0):
        """send body, return parse(reply data) of the first reply it accepts"""
        if self.dry:
            self.send(body)
            return None
        for _ in self.inp.iter_pending():
            pass
        self.send(body)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for m in self.inp.iter_pending():
                if m.type == "sysex":
                    r = parse(list(m.data))
                    if r:
                        return r
            time.sleep(0.005)
        return None

    def zoom(self, *b):
        self.send([0x52, 0x00, self.dev, *b])

    def read_patch(self):
        if self.dry:
            return [0] * 122
        r = self.ask([0x52, 0x00, self.dev, 0x29], lambda d: d if len(d) == 144 and d[3] == 0x28 else None)
        if not r:
            sys.exit("no patch dump (28) from the pedal")
        return unpack7(r[4:])

    def write_patch(self, rec):
        self.zoom(0x28, *pack7(rec))

    def param(self, slot, p, v):
        """p 0 = on/off, 1-9 = knob; stock 31 (slots 0-2 on this OS)"""
        self.zoom(0x31, slot, p + 1 if p else 0, v & 0x7F, v >> 7 & 0x7F)

    def bench(self):
        self.nonce = self.nonce + 1 & 0x7F
        return self.ask(BENCH + [self.nonce], parse_bench, 1.0)

    def window(self, fresh=2):
        """the numbers of the window `fresh` windows after now (the first may hold the change)"""
        if self.dry:
            self.bench()
            return None
        r = self.bench()
        w0 = r["win"] if r else None
        end = time.monotonic() + 3 + 1.5 * fresh
        while time.monotonic() < end:
            time.sleep(0.25)
            r = self.bench()
            if r and w0 is None:
                w0 = r["win"]
            elif r and (r["win"] - w0) & 0xFFFFFFFF >= fresh:
                return r
        sys.exit("no new DIAG window: is this MIDISTOMP firmware with SysEx 06?")


class Log:
    def __init__(self, path):
        self.f = open(path, "w", newline="", encoding="utf-8") if path else None
        self.w = csv.writer(self.f) if self.f else None
        if self.w:
            self.w.writerow(["time", "test", "effect", "param", "value", "on"] + WORDS)
        self.rows = []

    def add(self, test, effect, param, value, on, r):
        if r is None:
            return
        self.rows.append((effect, r))
        if self.w:
            self.w.writerow([time.strftime("%H:%M:%S"), test, effect, param, value, on] + [r[k] for k in WORDS])
            self.f.flush()
        pc = 100.0 / r["period"] if r["period"] else 0
        print("  %-8s %-6s %5s on=%s  slot1 %6d avg %6d worst (%4.1f%% / %4.1f%%)  audio max %4.1f%%  late %d"
              % (effect, param, value, on, r["cyc1"], r["cmax1"], r["cyc1"] * pc, r["cmax1"] * pc,
                 r["chmax"] * pc, r["late"]))

    def summary(self):
        by = {}
        for e, r in self.rows:
            by.setdefault(e, []).append(r)
        print("\n%-10s %8s %8s %8s %7s %9s" % ("effect", "avg", "avg max", "worst", "avg %", "declared"))
        for e, rs in by.items():
            avg = sum(r["cyc1"] for r in rs) / len(rs)
            hi, worst, per = max(r["cyc1"] for r in rs), max(r["cmax1"] for r in rs), rs[-1]["period"] or 54422
            print("%-10s %8d %8d %8d %6.1f%% %9.1f" % (e, avg, hi, worst, avg * 100 / per, rs[-1]["dsp1"] / 10))


def watch(pedal, log, seconds, test="watch"):
    end = time.monotonic() + seconds
    while True:
        r = pedal.window(1)
        log.add(test, "chain", "", "", "", r)
        if r:
            print("    audio %5d max %5d late %d late total %d" % (r["ch"], r["chmax"], r["late"], r["late_total"]))
        if pedal.dry or time.monotonic() > end:
            return


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["sweep", "chain", "watch"])
    ap.add_argument("effects", nargs="*", help="chain: effect names, slot 1 first")
    ap.add_argument("--pack", default=str(PACK), help="zoom-ms-zdl-effects-pack folder (manifests)")
    ap.add_argument("--only", help="sweep: these effects only, comma separated")
    ap.add_argument("--steps", type=int, default=3, help="sweep: values per knob, min to max")
    ap.add_argument("--seconds", type=float, default=30, help="watch: how long")
    ap.add_argument("--csv", default="dsp_bench.csv")
    ap.add_argument("--port")
    ap.add_argument("--dry-run", action="store_true", help="print the SysEx, send nothing")
    a = ap.parse_args(argv)

    pack = load_pack(a.pack) if a.mode != "watch" else {}
    pedal = Pedal(a.port, a.dry_run)
    log = Log(None if a.dry_run else a.csv)
    if a.mode == "watch":
        watch(pedal, log, a.seconds)
        return
    pedal.zoom(0x50)                                    # editor mode on: 31 needs it
    orig = pedal.read_patch()
    try:
        if a.mode == "chain":
            try:
                fx = [(pack[n.upper()], 1) for n in a.effects]
            except KeyError as e:
                sys.exit("not a pack effect: %s" % e)
            pedal.write_patch(build_chain(orig, fx))
            r = pedal.window()
            log.add("chain", "+".join(a.effects), "", "", 1, r)
            if r:
                print("  slots avg", [r["cyc%d" % i] for i in range(1, 7)], "worst", [r["cmax%d" % i] for i in range(1, 7)])
        else:
            names = [n.strip().upper() for n in a.only.split(",")] if a.only else list(pack)
            for n in names:
                m = pack[n]
                print(m["effect_name"])
                pedal.write_patch(build_chain(orig, [(m, 1)]))
                r = pedal.window()
                if r and r["dsp1"] == 0:
                    print("  not on the pedal (slot 1 empty or THRU): skipped")
                    continue
                log.add("on", m["effect_name"], "", "", 1, r)
                pedal.param(0, 0, 0)
                log.add("off", m["effect_name"], "", "", 0, pedal.window())
                pedal.param(0, 0, 1)
                for p, d in enumerate(m["params"][:9]):
                    for k in range(a.steps):
                        v = round(d["max"] * k / max(1, a.steps - 1))
                        pedal.param(0, p + 1, v)
                        log.add("knob", m["effect_name"], d["name"], v, 1, pedal.window())
                    pedal.param(0, p + 1, d["default"])
    finally:
        pedal.write_patch(orig)                         # the edit buffer as it was
        pedal.zoom(0x51)
    if a.mode == "sweep" and not a.dry_run:
        if input("\nLoad a full patch, start PERFORM and press Enter (s + Enter skips): ").strip().lower() != "s":
            watch(pedal, log, a.seconds, "perform")
    log.summary()


if __name__ == "__main__":
    main()
