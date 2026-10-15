import random
import re
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest

from zoomms import asm, patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/cdr-stereo.yaml")
LOOPER = patcher.load(ROOT / "patches/looper.yaml")
(SEC,) = PATCH["section"]
SITES = {w["addr"]: w for w in PATCH["write"]}
BOOT, STEREO_IN, CALL_LIST_NEXT = 0xC00F2800, 0xC00F2900, 0x1181BD78
BUFA, BUFB, STATE = 0x11F03B80, 0x11F03C00, 0x11F03C80
OUT_L, OUT_R, OUT_MAX = 0x11F03638, 0x11F03658, 0x11F03758
C = [0x7FF60000, 0x03000000, 0x50000000, 0x20247A42, 0x5FDB85BD,  # 70CDR in_combine
     0x1FFE3FE8, 0xE001C018, 0x1FFC7FD0, 0x05F05F4B]               # coefficients (0xC00EC528)
needs_binutils = pytest.mark.skipif(not asm.available(), reason="tic6x binutils not installed")


def section_bytes():
    return bytes.fromhex("".join(SEC["data"].split()))


@needs_binutils
def test_bytes_match_assembly_sources():
    for site in PATCH["write"]:
        if "source" in site:
            assert asm.assemble(ROOT / site["source"], site["addr"]).hex() == site["data"]
    assert asm.assemble(ROOT / SEC["source"], SEC["addr"], whole_packets=True) == section_bytes()


def callp_target(addr, data):
    word = int.from_bytes(bytes.fromhex(data), "little")
    disp = word >> 7 & 0x1FFFFF
    return (addr & ~31) + 4 * (disp - (1 << 21) if disp >> 20 else disp)


def test_boot_hook_and_hand_encoded_edits():
    boot = SITES[0xC00D47F8]
    assert callp_target(boot["addr"], boot["expect"]) == 0xC00C31A4  # McASP init
    assert callp_target(boot["addr"], boot["data"]) == BOOT
    old, new = (int.from_bytes(bytes.fromhex(boot[k]), "little") for k in ("expect", "data"))
    assert old & ~(0x1FFFFF << 7) == new & ~(0x1FFFFF << 7)
    # Compact halfwords: the 70CDR PINMUX10 instruction (set .S2 b0,20,20,b0) and mvk .S2 48,b0
    # (seen at 0xC009F524), so the GPIO init gives bank 3 DIR 0x1030.
    assert SITES[0x11818274]["data"] == "2390" and SITES[0xC00CE292]["data"] == "3310"


def test_section_fits_and_entry_points():
    hooks = LOOPER["section"][0]
    assert SEC["addr"] == BOOT >= hooks["addr"] + len(bytes.fromhex("".join(hooks["data"].split())))
    assert SEC["addr"] + len(section_bytes()) <= 0xC00F3000  # looper services block
    far = bytes.fromhex(SITES[0x1181BD6C]["data"])
    lo, hi = (int.from_bytes(far[i:i + 4], "little") >> 7 & 0xFFFF for i in (0, 4))
    assert hi << 16 | lo == STEREO_IN
    assert section_bytes()[STEREO_IN - BOOT:STEREO_IN - BOOT + 4] != bytes(4)


# --- A small cycle-level simulator for stereo_in, run against a Python model of the
# 70CDR stages (rx_deint 0x1181BB0C, in_combine 0x1181B680, to_float 0x1181B8C0). It
# checks the hand schedule (delay slots, register reuse), not the instruction semantics.

M32 = 0xFFFFFFFF


def s32(x):
    x &= M32
    return x - (1 << 32) if x >> 31 else x


def sat(x):
    return max(-(1 << 31), min((1 << 31) - 1, x)) & M32


def smpy32(a, b):
    return sat((s32(a) * s32(b)) >> 31)


def f32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def fl(w):
    return struct.unpack("<f", struct.pack("<I", w))[0]


OPS = {
    "smpy32": (4, lambda a, b: smpy32(a, b)),
    "mpysp": (4, lambda a, b: f32(fl(a) * fl(b))),
    "intsp": (4, lambda a: f32(float(s32(a)))),
    "add": (1, lambda a, b: (a + b) & M32),
    "sadd": (1, lambda a, b: sat(s32(a) + s32(b))),
    "ssub": (1, lambda a, b: sat(s32(a) - s32(b))),
    "sshl": (1, lambda a, n: sat(s32(a) << n)),
    "abs": (1, lambda a: sat(abs(s32(a)))),
    "or": (1, lambda a, b: a | b),
    "cmplt": (1, lambda a, b: int(s32(a) < s32(b))),
    "cmpgtu": (1, lambda a, b: int((a & M32) > (b & M32))),
}


def disassemble(code, addr):
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(code)
        f.flush()
        out = subprocess.run([asm.PREFIX + "objdump", "-D", "-b", "binary", "-m", "tic6x", "-EL",
                              f"--adjust-vma={addr:#x}", f.name], check=True, capture_output=True, text=True).stdout
    packets, pc = {}, None
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]{8}):\s+[0-9a-f]{8}\s+(.*)", line)
        if not m:
            continue
        a, text = int(m[1], 16), m[2].split(";")[0].strip()
        if text.startswith("||"):
            packets[pc].append(text[2:].strip())
        else:
            pc = a
            packets[pc] = [text]
    return packets


class Cpu:
    def __init__(self, mem):
        self.r, self.mem, self.pending, self.cycle = {}, mem, [], 0

    def reg(self, name):
        return self.r.get(name, 0)

    def val(self, tok):
        return self.reg(tok) if re.fullmatch(r"[ab]\d+", tok) else int(tok, 0) & M32

    def addr(self, tok, size=4):
        m = re.fullmatch(r"\*(\+\+|--)?(\+|-)?([ab]\d+)(\+\+|--)?(?:\((-?\d+)\)|\[(\d+)\])?", tok)
        pre, sign, base, post, off, idx = m.groups()
        off = int(off) if off else (int(idx) * size if idx else (size if pre or post else 0))
        b = self.reg(base)
        if pre:
            b = (b + off if pre == "++" else b - off) & M32
            self.write(base, b, 1)
            return b
        if post:
            self.write(base, (b + off if post == "++" else b - off) & M32, 1)
            return b
        return (b - off if sign == "-" else b + off) & M32

    def write(self, reg, value, delay):
        self.pending.append((self.cycle + delay, reg, value))

    def step(self, packet):
        """Run one execute packet; returns (nop cycles, branch target or None)."""
        branch, nops, stores = None, 1, []
        for ins in packet:
            m = re.match(r"\[(!?)([ab][0-2])\]\s*(.*)", ins)
            if m:
                if (self.reg(m[2]) != 0) == (m[1] == "!"):
                    continue
                ins = m[3]
            op, _, rest = ins.partition(" ")
            args = [a.strip() for a in re.sub(r"^\.\w+\s*", "", rest.strip()).split(",")] if rest else []
            if op == "nop":
                nops = int(args[0]) if args else 1
            elif op == "mvk":
                self.write(args[1], int(args[0]) & M32, 1)
            elif op == "mvkh":
                self.write(args[1], (int(args[0]) & 0xFFFF0000) | (self.reg(args[1]) & 0xFFFF), 1)
            elif op == "ldw":
                a = self.addr(args[0])
                self.write(args[1], self.mem.get(a, 0), 5)
            elif op == "stw":
                stores.append((self.addr(args[1]), self.reg(args[0])))
            elif op == "addk":
                self.write(args[1], (self.reg(args[1]) + int(args[0])) & M32, 1)
            elif op == "b":
                branch = self.val(args[0])
            elif op in OPS:
                lat, fn = OPS[op]
                self.write(args[-1], fn(*(self.val(a) for a in args[:-1])), lat)
            else:
                raise AssertionError(f"simulator lacks {ins!r}")
        self.mem.update(stores)
        return nops, branch

    def tick(self):
        self.cycle += 1
        due = [p for p in self.pending if p[0] <= self.cycle]
        assert len({p[1] for p in due if p[0] == self.cycle}) == len([p for p in due if p[0] == self.cycle]), \
            f"two results land in one register in cycle {self.cycle}"
        for _, reg, value in sorted(due):
            self.r[reg] = value
        self.pending = [p for p in self.pending if p[0] > self.cycle]


def run_stereo_in(packets, mem):
    cpu, pc, taken = Cpu(mem), STEREO_IN, []
    while pc != CALL_LIST_NEXT:
        nops, branch = cpu.step(packets[pc])
        if branch is not None:
            taken.append((cpu.cycle + 6, branch))
        order = sorted(packets)
        nxt = order[order.index(pc) + 1] if pc != order[-1] else None
        for _ in range(nops):
            cpu.tick()
            due = [t for t in taken if t[0] == cpu.cycle]
            if due:
                taken.remove(due[0])
                nxt = due[0][1]
                break
        pc = nxt
        assert cpu.cycle < 2000, "stereo_in did not return"
    return cpu.cycle


def model(frames, st):
    """The 70CDR stages for one block. st: [peak, env, y', z'] per side, updated in place."""
    neg = lambda w: smpy32(w, 0x80000000)
    out = {"L": [], "R": [], "max": []}
    for f in frames:
        peaks, vals = [], []
        for side, (i0, i1) in (("L", (1, 3)), ("R", (0, 2))):  # AXR5 pair = L, AXR4 pair = R
            x0, x1 = neg(f[i0]), neg(f[i1])
            s = st[side]
            env = (smpy32(s[1], C[4]) + smpy32(sat(abs(s32(x1))), C[3])) & M32
            t = smpy32(s[0], C[0])
            peak = env if s32(t) < s32(env) else t
            d = (sat(s32(sat(s32(peak) - s32(C[1]))) - (1 << 31)) + 0x80000000) & M32
            g = sat(s32(smpy32(d, C[2])) << 8)
            h = sat(abs(s32(sat(s32(g) - 0x7FFFFFFF))))
            y = sat(s32(smpy32(g, x1)) + s32(smpy32(h, smpy32(x0, C[8]))))
            v = sat(s32(sat(s32(smpy32(y, C[5])) + s32(smpy32(s[2], C[6])))) + s32(smpy32(s[3], C[7])))
            z = sat(s32(v) << 2)
            s[:] = [peak, env, y, z]
            fz = f32(fl(f32(float(s32(z)))) * fl(0x30000000))
            out[side].append(fz)
            peaks.append(peak)
            vals.append(fz)
        out["max"].append(vals[1] if s32(peaks[0]) < s32(peaks[1]) else vals[0])
    return out


@needs_binutils
def test_stereo_in_matches_the_70cdr_stages():
    packets = disassemble(section_bytes()[STEREO_IN - BOOT:], STEREO_IN)
    rnd = random.Random(70)
    mem = {STATE + 4 * i: 0 for i in range(8)}
    st = {"L": [0] * 4, "R": [0] * 4}
    picked = set()
    for block in range(24):
        if block < 8:  # quiet: the high-gain slot (x0) carries the signal
            frames = [[rnd.randint(-1 << 24, 1 << 24) & M32 for _ in range(4)] for _ in range(8)]
        else:          # loud, up to full scale; L only, R only or both, so the louder side changes
            amp = (1 << 31) - 1 if block % 4 else 1 << 26
            loud = ({1, 3}, {0, 2}, {0, 1, 2, 3})[block % 3]  # frame words: R = 0, 2; L = 1, 3
            frames = [[rnd.randint(-amp, amp) & M32 if k in loud else rnd.randint(-99, 99) & M32
                       for k in range(4)] for _ in range(8)]
        buf = BUFB if block % 2 else BUFA   # the buffer the DMA finished
        for n, f in enumerate(frames):
            for k, w in enumerate(f):
                mem[buf + 16 * n + 4 * k] = w
        mem[0x01C0400C] = (BUFA if block % 2 else BUFB) + 8 * rnd.randrange(16)  # DMA in the other one
        cycles = run_stereo_in(packets, mem)
        want = model(frames, st)
        picked |= {"L" if m == l else "R" for m, l in zip(want["max"], want["L"])}
        for name, base in (("L", OUT_L), ("R", OUT_R), ("max", OUT_MAX)):
            assert [mem[base + 4 * n] for n in range(8)] == want[name], (block, name)
        assert [mem[STATE + 4 * i] for i in range(8)] == st["L"] + st["R"]
    assert picked == {"L", "R"}
    assert cycles < 600  # about 0.6 % of a 456 MHz DSP at 44.1 kHz / 8
