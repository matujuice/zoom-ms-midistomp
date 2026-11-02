"""Small cycle-stepped C674x interpreter for the MS-70CDR OS image.

Decoding is done by TI's own disassembler: dis6x (CGT 8.5.0) disassembles the image (wrapped
as an ELF with Tag_ISA = C674x by elf_attr.py, so compact 16-bit instructions and fetch packet
headers are expanded). This module parses that listing and executes it:
  - execute packets (|| chains), one cycle each; NOP n / BNOP n / CALLP occupy their cycles,
  - delayed register writes (loads 4, 16-bit multiplies 1, MPY32 3, branches 5 delay slots),
    a branch firing during a multi-cycle NOP ends it,
  - predication, read at issue,
  - PROT fetch packets (header 'p'): every load in them is followed by 4 implied NOP cycles,
  - SPLOOP/SPLOOPD/SPLOOPW with SPKERNEL (no SPMASK'ed epilog/prolog subtleties beyond
    the plain buffer replay; see run_sploop).
Unknown mnemonics raise, so nothing is silently skipped.
"""
from __future__ import annotations

import math
import re
import struct

M32 = 0xFFFFFFFF


def s32(x):
    x &= M32
    return x - (1 << 32) if x & 0x80000000 else x


def s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def u16(x):
    return x & 0xFFFF


def reg_index(name):
    return (0 if name[0] == "A" else 32) + int(name[1:])


LINE = re.compile(r"^([0-9a-f]{8}) +([0-9a-f]{4,8}) +(\|\|)? *(?:\[ ?(!?)([AB]\d+)\])? *(\S+)\s*(.*)$")


class Instr:
    __slots__ = ("addr", "size", "par", "pred", "mnem", "unit", "ops", "text", "prot", "fn", "load", "masked")

    def __repr__(self):
        return f"{self.addr:08x} {self.text}"


def split_ops(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_listing(path):
    instrs = {}
    prot_packets = set()
    for line in open(path, encoding="latin-1"):
        masked = "||^" in line  # dis6x marks SPMASKed instructions with ^
        m = LINE.match(line.rstrip("\n").replace("||^", "|| "))
        if not m:
            continue
        addr = int(m.group(1), 16)
        mn = m.group(6)
        if mn == ".fphead":
            if m.group(7).split(",")[0].strip() == "p":
                prot_packets.add(addr & ~0x1F)
            continue
        if mn.startswith("."):
            continue
        i = Instr()
        i.addr = addr
        i.size = len(m.group(2)) // 2
        i.par = bool(m.group(3))
        i.pred = (reg_index(m.group(5)), m.group(4) == "!") if m.group(5) else None
        base, _, unit = mn.partition(".")
        i.mnem, i.unit = base, unit
        i.ops = split_ops(m.group(7))
        i.masked = masked
        i.text = f"{'|| ' if i.par else ''}{('[' + m.group(4) + m.group(5) + '] ') if m.group(5) else ''}{mn} {m.group(7)}"
        instrs[addr] = i
    for i in instrs.values():
        i.prot = (i.addr & ~0x1F) in prot_packets
    return instrs


MEM_RE = re.compile(r"^\*(\+\+|--|\+|-)?([AB]\d+)(\+\+|--)?(?:\[(.+)\]|\((.+)\))?$")

LOADS = {"LDB": (1, True), "LDBU": (1, False), "LDH": (2, True), "LDHU": (2, False), "LDW": (4, False),
         "LDNW": (4, False), "LDDW": (8, False), "LDNDW": (8, False)}
STORES = {"STB": 1, "STH": 2, "STW": 4, "STNW": 4, "STDW": 8, "STNDW": 8}


class Halt(Exception):
    pass


class CPU:
    def __init__(self, listing, mem):
        self.I = listing
        self.mem = mem
        self.R = [0] * 64
        self.ctrl = {}
        self.t = 0
        self.wq = {}           # cycle -> [(reg, value)]
        self.branch = {}       # cycle -> target (branches in delay slots of others are legal)
        self.addrs = sorted(listing)
        self.eps = {}
        self.trace = None
        self.hooks = {}        # pc -> fn(cpu) returning True to skip (fn must set pc)
        self.count = 0
        self.ilc = 0

    # ---- memory ----
    def rd(self, a, n):
        return self.mem.read(a & M32, n)

    def wr(self, a, n, v):
        self.mem.write(a & M32, n, v)

    # ---- decode an execute packet ----
    def ep_at(self, pc):
        ep = self.eps.get(pc)
        if ep is not None:
            return ep
        if pc not in self.I:
            raise Halt(f"no instruction at {pc:08x}")
        import bisect
        k = bisect.bisect_left(self.addrs, pc)
        lst = [self.I[pc]]
        if lst[0].par:
            raise Halt(f"branch into the middle of an execute packet at {pc:08x}")
        k += 1
        while k < len(self.addrs) and self.I[self.addrs[k]].par:
            lst.append(self.I[self.addrs[k]])
            k += 1
        nxt = self.addrs[k] if k < len(self.addrs) else None
        for ins in lst:
            if getattr(ins, "fn", None) is None:
                ins.fn = self.compile(ins, nxt)
        ep = (lst, nxt)
        self.eps[pc] = ep
        return ep

    # ---- operand helpers ----
    def src(self, op):
        """-> function returning the value of a register or constant operand."""
        R = self.R
        if re.fullmatch(r"[AB]\d+", op):
            r = reg_index(op)
            return lambda: R[r]
        v = int(op, 0) & M32
        return lambda: v

    def pair(self, op):
        hi, lo = op.split(":")
        return reg_index(hi), reg_index(lo)

    def mem_op(self, op, size):
        m = MEM_RE.match(op)
        if not m:
            raise Halt(f"memory operand {op}")
        pre, base, post, sc, un = m.groups()
        b = reg_index(base)
        offs = sc if sc is not None else un
        scale = size if sc is not None else 1
        if offs is None:
            offs = "1" if (pre in ("++", "--") or post) else "0"
            scale = size
        R = self.R
        if re.fullmatch(r"[AB]\d+", offs):
            o = reg_index(offs)
            off = lambda: (R[o] * scale) & M32
        else:
            c = (int(offs, 0) * scale) & M32
            off = lambda: c

        def ea():
            bv = R[b]
            ov = off()
            if pre == "+":
                return (bv + ov) & M32, None
            if pre == "-":
                return (bv - ov) & M32, None
            if pre == "++":
                n = (bv + ov) & M32
                return n, (b, n)
            if pre == "--":
                n = (bv - ov) & M32
                return n, (b, n)
            if post == "++":
                return bv, (b, (bv + ov) & M32)
            if post == "--":
                return bv, (b, (bv - ov) & M32)
            return (bv + ov) & M32, None  # "*R[n]" = "*+R[n]"
        return ea

    # ---- compile one instruction into fn(cpu) -> list of side effects via self.sched ----
    def compile(self, ins, nxt):
        mn, ops, R = ins.mnem, ins.ops, self.R
        sched = self.sched
        ins.load = False

        def w(dst_name, f, delay=0):
            d = reg_index(dst_name)
            return lambda: sched(d, f() & M32, delay)

        if mn in LOADS:
            size, signed = LOADS[mn]
            ea = self.mem_op(ops[0], size)
            ins.load = True
            if size == 8:
                hi, lo = self.pair(ops[1])

                def f():
                    a, upd = ea()
                    v = self.rd(a, 8)
                    if upd:
                        sched(*upd, 0)
                    sched(lo, v & M32, 4)
                    sched(hi, v >> 32, 4)
                return f
            d = reg_index(ops[1])

            def f():
                a, upd = ea()
                v = self.rd(a, size)
                if signed:
                    bits = size * 8
                    if v & (1 << (bits - 1)):
                        v -= 1 << bits
                if upd:
                    sched(*upd, 0)
                sched(d, v & M32, 4)
            return f
        if mn in STORES:
            size = STORES[mn]
            ea = self.mem_op(ops[1], size)
            if size == 8:
                hi, lo = self.pair(ops[0])

                def f():
                    a, upd = ea()
                    self.wr(a, 8, R[lo] | (R[hi] << 32))
                    if upd:
                        sched(*upd, 0)
                return f
            s = reg_index(ops[0])

            def f():
                a, upd = ea()
                self.wr(a, size, R[s])
                if upd:
                    sched(*upd, 0)
            return f
        if mn == "NOP" or mn in ("DINT", "RINT", "SPMASK", "SPMASKR", "PLD"):
            return lambda: None
        if mn == "MVK":
            return w(ops[1], self.src(ops[0]))
        if mn == "MVKH":
            c = int(ops[0], 0) & 0xFFFF0000
            d = reg_index(ops[1])
            return lambda: sched(d, (R[d] & 0xFFFF) | c, 0)  # reads at issue
        if mn == "MVKLH":
            c = (int(ops[0], 0) & 0xFFFF) << 16
            d = reg_index(ops[1])
            return lambda: sched(d, (R[d] & 0xFFFF) | c, 0)
        if mn in ("MV", "MVD"):
            if ":" in ops[0]:
                h1, l1 = self.pair(ops[0]); h2, l2 = self.pair(ops[1])
                return lambda: (sched(l2, R[l1], 0), sched(h2, R[h1], 0))
            return w(ops[1], self.src(ops[0]), 3 if mn == "MVD" else 0)
        if mn == "DMV":
            a, b = self.src(ops[0]), self.src(ops[1]); h, l = self.pair(ops[2])
            return lambda: (sched(h, a(), 0), sched(l, b(), 0))
        if mn == "ZERO":
            if ":" in ops[0]:
                h, l = self.pair(ops[0])
                return lambda: (sched(h, 0, 0), sched(l, 0, 0))
            return w(ops[0], lambda: 0)
        if mn in ("B", "BNOP", "CALLP"):
            tgt = ops[0]
            if tgt in ("IRP", "NRP"):
                return lambda: self.set_branch(self.ctrl.get(tgt, 0))
            if re.fullmatch(r"[AB]\d+", tgt):
                r = reg_index(tgt)
                f = lambda: self.set_branch(R[r])
            else:
                v = int(tgt, 0)
                f = lambda: self.set_branch(v)
            if mn == "CALLP":
                d = reg_index(ops[1])
                return lambda: (f(), sched(d, nxt, 0))
            return f
        if mn == "ADDKPC":
            d = reg_index(ops[1]); v = int(ops[0], 0)
            return lambda: sched(d, v, 0)
        if mn in ("BDEC", "BPOS"):
            v = int(ops[0], 0); r = reg_index(ops[1])

            def f():
                x = s32(R[r])
                if x >= 0:
                    self.set_branch(v)
                    if mn == "BDEC":
                        sched(r, x - 1, 0)
            return f
        if mn == "MVC":
            a, b = ops
            if re.fullmatch(r"[AB]\d+", a):
                s = reg_index(a)

                def f():
                    self.ctrl[b] = R[s]
                    if b == "ILC":
                        self.ilc = R[s]
                return f
            d = reg_index(b)

            def f():
                v = self.t if a == "TSCL" else 0 if a == "TSCH" else self.ctrl.get(a, 0)
                sched(d, v, 0)
            return f
        if mn in ("SPLOOP", "SPLOOPD", "SPLOOPW", "SPKERNEL", "SPKERNELR"):
            return lambda: None  # handled by the run loop
        if mn == "ADDK":
            c = int(ops[0], 0); d = reg_index(ops[1])
            return lambda: sched(d, R[d] + c, 0)
        three = len(ops) == 3
        if mn in DP:  # a pair operand is a double (hi:lo), a single register an int / float bits
            fn, lat = DP[mn]
            srcs = [(lambda h, l: lambda: _d(R[l] | R[h] << 32))(*self.pair(o)) if ":" in o else self.src(o) for o in ops[:-1]]
            if ":" in ops[-1]:
                h, l = self.pair(ops[-1])

                def f():
                    v = _db(fn(*(s() for s in srcs)))
                    sched(l, v & M32, lat); sched(h, v >> 32, lat)
                return f
            return w(ops[-1], lambda: fn(*(s() for s in srcs)), lat)
        if mn in ALU2 and len(ops) == 2:
            a = self.src(ops[0]); fn = ALU2[mn]
            if ":" in ops[1]:
                raise Halt(f"long op {ins}")
            return w(ops[1], lambda: fn(a()), LAT.get(mn, 0))
        if (mn in ALU or mn in LONG) and three:
            if ":" in ops[2] or ":" in ops[0] or ":" in ops[1]:
                if mn in LONG:
                    a, b = self.src(ops[0]), self.src(ops[1]); h, l = self.pair(ops[2]); fn = LONG[mn]; lat = LAT.get(mn, 0)

                    def f():
                        v = fn(a(), b()) & 0xFFFFFFFFFFFFFFFF
                        sched(l, v & M32, lat); sched(h, v >> 32, lat)
                    return f
                raise Halt(f"long op {ins}")
            a, b = self.src(ops[0]), self.src(ops[1]); fn = ALU[mn]
            return w(ops[2], lambda: fn(a(), b()), LAT.get(mn, 0))
        if mn in ("EXT", "EXTU", "SET", "CLR") and len(ops) == 4:
            a = self.src(ops[0]); c1 = int(ops[1], 0); c2 = int(ops[2], 0); fn = FIELD[mn]
            return w(ops[3], lambda: fn(a(), c1, c2))
        if mn in ("EXT", "EXTU", "SET", "CLR") and three:
            a, b = self.src(ops[0]), self.src(ops[1]); fn = FIELD[mn]
            return w(ops[2], lambda: fn(a(), (b() >> 5) & 31, b() & 31))
        raise_ = ins

        def bad():
            raise Halt(f"unimplemented: {raise_}")
        return bad

    def sched(self, reg, val, delay):
        self.wq.setdefault(self.t + delay, []).append((reg, val & M32))

    def set_branch(self, target):
        self.branch[self.t + 5] = target & M32

    def end_cycle(self):
        lst = self.wq.pop(self.t, None)
        if lst:
            for r, v in lst:
                self.R[r] = v
        fired = None
        if self.branch:
            fired = self.branch.pop(self.t, None)
        self.t += 1
        return fired

    def issue(self, lst):
        """Execute one packet's instructions at cycle self.t. -> extra cycles it occupies."""
        R = self.R
        cycles = 1
        loads = False
        for ins in lst:
            if self.trace:
                self.trace(self, ins)
            p = ins.pred
            if p is not None and ((R[p[0]] == 0) != p[1]):
                if ins.mnem in ("NOP", "BNOP", "ADDKPC"):  # the NOP part still runs
                    pass
                else:
                    continue
            else:
                ins.fn()
            if ins.load and ins.prot:
                loads = True
            if ins.mnem == "NOP":
                cycles = max(cycles, int(ins.ops[0], 0) if ins.ops else 1)
            elif ins.mnem == "BNOP":
                cycles = max(cycles, 1 + int(ins.ops[1], 0))
            elif ins.mnem == "ADDKPC":
                cycles = max(cycles, 1 + int(ins.ops[2], 0))
            elif ins.mnem == "CALLP":
                cycles = max(cycles, 6)
        if loads:
            cycles += 4
        return cycles

    def run(self, pc, stop, max_ep=50_000_000):
        while pc != stop:
            h = self.hooks.get(pc)
            if h is not None and not self.branch:
                pc = h(self)
                continue
            lst, nxt = self.ep_at(pc)
            self.count += 1
            if self.count > max_ep:
                raise Halt("too many packets")
            if lst[0].mnem.startswith("SPLOOP"):
                pc = self.run_sploop(lst, nxt)
                continue
            n = self.issue(lst)
            target = None
            for _ in range(n):
                f = self.end_cycle()
                if f is not None:
                    target = f
                    break
            pc = target if target is not None else nxt
        # drain pending writes
        for _ in range(8):
            self.end_cycle()
        return pc

    def run_sploop(self, lst, nxt):
        """SPLOOP ii: collect the loop body packets up to SPKERNEL and run it ILC times
        (SPLOOP/SPLOOPD) or until the predicate register is 0 (SPLOOPW), one iteration per
        ii cycles, overlapping as the hardware does (each instruction keeps its stage)."""
        head = lst[0]
        ii = int(head.ops[0], 0)
        # gather body packets
        body = []  # (cycle offset, [instrs])
        pc = nxt
        first = [i for i in lst[1:]]
        for i in first:  # in parallel with SPLOOP: runs once, not buffered (memset in cinit RLE proves it)
            i.masked = True
        cyc = 0
        prot = lambda l: 4 if any(i.load and i.prot for i in l) else 0  # PROT: loads get implied NOP 4
        if first:
            body.append((cyc, first))
            cyc += 1 + prot(first)
        elif self.end_cycle() is not None:  # the SPLOOP packet takes its own cycle (printf's strlen needs a load landed by then)
            raise Halt("branch at sploop")
        while True:
            l2, n2 = self.ep_at(pc)
            if l2[0].mnem == "NOP":
                cyc += int(l2[0].ops[0], 0) if l2[0].ops else 1
                pc = n2
                continue
            body.append((cyc, [i for i in l2 if i.mnem not in ("SPKERNEL", "SPKERNELR")]))
            cyc += 1 + prot(l2)
            if any(i.mnem in ("SPKERNEL", "SPKERNELR") for i in l2):
                after = n2
                break
            pc = n2
        length = cyc
        if head.mnem == "SPLOOPW":
            pr = head.pred
            count = None
        else:
            count = self.ilc
            if head.pred is not None and ((self.R[head.pred[0]] == 0) != head.pred[1]):
                return nxt  # loop skipped entirely: hardware still fetches, ignore
        if head.mnem == "SPLOOPD":
            # SPLOOPD skips the termination test for the first 4 cycles: ILC + ceil(4/ii) iterations
            # (matches the OS: 7-column icons load ILC=6 at ii=8, 8-byte glyphs ILC=4 at ii=1)
            count += -(-4 // ii)
        # simulate: iteration k starts at cycle base + k*ii; instruction at offset o issues at base + k*ii + o
        base = self.t
        events = {}
        k = 0
        stop_issue = None
        R = self.R
        while True:
            if count is not None and k >= count:
                break
            start = base + k * ii
            if stop_issue is not None and start >= stop_issue:
                break
            for o, ins_list in body:
                # SPMASK'ed instructions run once (not stored in the loop buffer)
                events.setdefault(start + o, []).append(ins_list if k == 0 else [i for i in ins_list if not i.masked])
            k += 1
            # SPLOOPW: termination tested at each iteration's first stage end? model: test predicate
            # when the next iteration would start, after running up to that cycle.
            if count is None:
                # run until the next start, then test the condition register
                self._run_events(events, start + ii)
                if (R[pr[0]] == 0) != pr[1]:
                    stop_issue = start + ii
                    break
            if k > 1_000_000:
                raise Halt("sploop runaway")
        if count is not None:
            pass
        # SPLOOPW: an iteration in flight when the condition fails is abandoned (no epilog)
        if count is None:
            events = {c: v for c, v in events.items() if c < stop_issue}
        end = max(events) + 1 if events else self.t
        self._run_events(events, end)
        return after

    def _run_events(self, events, until):
        while self.t < until:
            for ins_list in events.pop(self.t, []):
                for ins in ins_list:
                    p = ins.pred
                    if p is not None and ((self.R[p[0]] == 0) != p[1]):
                        continue
                    if self.trace:
                        self.trace(self, ins)
                    ins.fn()
            f = self.end_cycle()
            if f is not None:
                raise Halt("branch inside sploop")


def _mpy(a, b):
    return s16(a) * s16(b)


ALU = {
    "ADD": lambda a, b: a + b, "ADDU": lambda a, b: a + b, "SUB": lambda a, b: a - b, "SUBU": lambda a, b: a - b,
    "AND": lambda a, b: a & b, "OR": lambda a, b: a | b, "XOR": lambda a, b: a ^ b, "ANDN": lambda a, b: a & ~b,
    "ADDAB": lambda a, b: a + b, "ADDAH": lambda a, b: a + (b << 1), "ADDAW": lambda a, b: a + (b << 2),
    "ADDAD": lambda a, b: a + (b << 3), "SUBAB": lambda a, b: a - b, "SUBAH": lambda a, b: a - (b << 1),
    "SUBAW": lambda a, b: a - (b << 2),
    "SHL": lambda a, b: a << (b & 63) if (b & 63) < 32 else 0,
    "SHR": lambda a, b: s32(a) >> min(b & 63, 31), "SHRU": lambda a, b: (a & M32) >> (b & 63) if (b & 63) < 32 else 0,
    "CMPEQ": lambda a, b: int((a & M32) == (b & M32)),
    "CMPGT": lambda a, b: int(s32(a) > s32(b)), "CMPLT": lambda a, b: int(s32(a) < s32(b)),
    "CMPGTU": lambda a, b: int((a & M32) > (b & M32)), "CMPLTU": lambda a, b: int((a & M32) < (b & M32)),
    "MPY": _mpy, "MPYU": lambda a, b: u16(a) * u16(b), "MPYSU": lambda a, b: s16(a) * u16(b),
    "MPYUS": lambda a, b: u16(a) * s16(b),
    "MPYH": lambda a, b: s16(a >> 16) * s16(b >> 16), "MPYHU": lambda a, b: u16(a >> 16) * u16(b >> 16),
    "MPYHL": lambda a, b: s16(a >> 16) * s16(b), "MPYLH": lambda a, b: s16(a) * s16(b >> 16),
    "MPYHLU": lambda a, b: u16(a >> 16) * u16(b), "MPYLHU": lambda a, b: u16(a) * u16(b >> 16),
    "MPYI": lambda a, b: s32(a) * s32(b), "MPY32": lambda a, b: s32(a) * s32(b),
    "MIN2": None, "MAX2": None,
    "PACK2": lambda a, b: ((a & 0xFFFF) << 16) | (b & 0xFFFF),
    "PACKH2": lambda a, b: (a & 0xFFFF0000) | ((b >> 16) & 0xFFFF),
    "PACKLH2": lambda a, b: ((a & 0xFFFF) << 16) | ((b >> 16) & 0xFFFF),
    "PACKHL2": lambda a, b: (a & 0xFFFF0000) | (b & 0xFFFF),
    "LMBD": lambda a, b: 32 - ((b if a & 1 else ~b) & M32).bit_length(),
    "SUBC": lambda a, b: ((((a - b) & M32) << 1) + 1) if (a & M32) >= (b & M32) else (a << 1),
    "PACKL4": lambda a, b: (((a >> 16) & 0xFF) << 24) | ((a & 0xFF) << 16) | (((b >> 16) & 0xFF) << 8) | (b & 0xFF),
    "PACKH4": lambda a, b: (((a >> 24) & 0xFF) << 24) | (((a >> 8) & 0xFF) << 16) | (((b >> 24) & 0xFF) << 8) | ((b >> 8) & 0xFF),
    "SADD": lambda a, b: max(-2**31, min(2**31 - 1, s32(a) + s32(b))),
    "SSUB": lambda a, b: max(-2**31, min(2**31 - 1, s32(a) - s32(b))),
    "ROTL": lambda a, b: ((a << (b & 31)) | ((a & M32) >> (32 - (b & 31)))) if b & 31 else a,
}
ALU = {k: v for k, v in ALU.items() if v is not None}


def _f(a):  # bits -> float32 value
    return struct.unpack("<f", struct.pack("<I", a & M32))[0]


def _b(x):  # value -> float32 bits (rounded to nearest)
    return struct.unpack("<I", struct.pack("<f", x))[0]


ALU.update({"ADDSP": lambda a, b: _b(_f(a) + _f(b)), "SUBSP": lambda a, b: _b(_f(a) - _f(b)),
            "MPYSP": lambda a, b: _b(_f(a) * _f(b)), "CMPGTSP": lambda a, b: int(_f(a) > _f(b)),
            "CMPLTSP": lambda a, b: int(_f(a) < _f(b)), "CMPEQSP": lambda a, b: int(_f(a) == _f(b))})
def _d(a):  # 64 bits -> double
    return struct.unpack("<d", struct.pack("<Q", a))[0]


def _db(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


# double ops: (fn on python values, delay slots); results to a single register are int / float32 bits
DP = {"INTDP": (lambda a: float(s32(a)), 4), "INTDPU": (lambda a: float(a & M32), 4), "SPDP": (lambda a: _f(a), 1),
      "DPSP": (lambda a: _b(a), 3), "DPINT": (lambda a: round(a), 3), "DPTRUNC": (lambda a: int(a), 3),
      "MPYDP": (lambda a, b: a * b, 9), "ADDDP": (lambda a, b: a + b, 6), "SUBDP": (lambda a, b: a - b, 6),
      "CMPGTDP": (lambda a, b: int(a > b), 1), "CMPLTDP": (lambda a, b: int(a < b), 1), "CMPEQDP": (lambda a, b: int(a == b), 1),
      "ABSDP": (abs, 1), "RSQRDP": (lambda a: a ** -0.5 if a > 0 else math.inf, 1),
      "RCPDP": (lambda a: 1 / a if a else math.copysign(math.inf, a), 1)}  # exact; stock refines it by Newton steps
LONG = {"SUBU": lambda a, b: ((a & M32) - (b & M32)) & 0xFFFFFFFFFF, "ADDU": lambda a, b: ((a & M32) + (b & M32)) & 0xFFFFFFFFFF, "MPY32": lambda a, b: s32(a) * s32(b), "MPY32U": lambda a, b: (a & M32) * (b & M32),
        "MPYLI": lambda a, b: s16(a) * s32(b), "MPYHI": lambda a, b: s16(a >> 16) * s32(b),
        "MPY32SU": lambda a, b: s32(a) * (b & M32), "MPY32US": lambda a, b: (a & M32) * s32(b)}
ALU2 = {"NEG": lambda a: -a, "NOT": lambda a: ~a, "ABS": lambda a: abs(s32(a)),
        "NORM": lambda a: 31 - (s32(a) ^ (s32(a) >> 31)).bit_length(),
        "INTSP": lambda a: _b(s32(a)), "INTSPU": lambda a: _b(a & M32),
        "SPINT": lambda a: round(_f(a)), "SPTRUNC": lambda a: int(_f(a))}   # SPINT: FADCR round to nearest
ALU2 = {k: v for k, v in ALU2.items() if v is not None}
LAT = {"MPY": 1, "MPYU": 1, "MPYSU": 1, "MPYUS": 1, "MPYH": 1, "MPYHU": 1, "MPYHL": 1, "MPYLH": 1,
       "MPYHLU": 1, "MPYLHU": 1, "MPYI": 8, "MPY32": 3, "MPY32U": 3, "MPYLI": 3, "MPYHI": 3,
       "MPY32SU": 3, "MPY32US": 3, "ADDSP": 3, "SUBSP": 3, "MPYSP": 3, "INTSP": 3, "INTSPU": 3, "SPINT": 3,
       "SPTRUNC": 3}


def _ext(v, a, b):
    v = (v << a) & M32
    return s32(v) >> b


def _extu(v, a, b):
    return ((v << a) & M32) >> b


def _mask(lo, hi):
    if hi < lo:
        return 0
    return ((1 << (hi - lo + 1)) - 1) << lo


FIELD = {"EXT": _ext, "EXTU": _extu,
         "SET": lambda v, lo, hi: v | _mask(lo, hi), "CLR": lambda v, lo, hi: v & ~_mask(lo, hi)}


class Memory:
    """Sparse byte memory, 64 KB pages; 0xC8xxxxxx (uncached DDR alias) maps onto 0xC0xxxxxx."""

    def __init__(self):
        self.pages = {}
        self.log = None

    def _page(self, a):
        if (a >> 24) == 0xC8:
            a &= 0xC0FFFFFF
        p = self.pages.get(a >> 16)
        if p is None:
            p = self.pages[a >> 16] = bytearray(65536)
            if self.log:
                self.log(a)
        return p, a & 0xFFFF

    def read(self, a, n):
        p, o = self._page(a)
        if o + n <= 65536:
            return int.from_bytes(p[o:o + n], "little")
        return int.from_bytes(bytes(self.read(a + i, 1) for i in range(n)), "little")

    def write(self, a, n, v):
        if self.watch and self.watch(a, n, v):
            return
        p, o = self._page(a)
        b = (v & ((1 << (8 * n)) - 1)).to_bytes(n, "little")
        if o + n <= 65536:
            p[o:o + n] = b
        else:
            for i in range(n):
                self.write(a + i, 1, b[i])

    watch = None

    def load(self, path):
        b = open(path, "rb").read()
        o = 0
        while o < len(b):
            a, n = struct.unpack_from("<II", b, o)
            d = b[o + 8:o + 8 + n]
            for i in range(0, n, 4096):
                chunk = d[i:i + 4096]
                p, off = self._page(a + i)
                if off + len(chunk) <= 65536:
                    p[off:off + len(chunk)] = chunk
                else:
                    for j, x in enumerate(chunk):
                        self.write(a + i + j, 1, x)
            o += 8 + n
