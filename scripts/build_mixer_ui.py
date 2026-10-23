"""Build the Mixer Mode sections of patches/mixer-m2.yaml with TI CGT 8.5:
the M3b Effect Chain C (chain_vec.asm + chain_keys.c + chain_draw.c, linked at
0xC00F8000) and mixer.S (0xC00F6000). Compares them with the yaml, or --write
replaces the yaml hex. --stub draws a blank screen (chain_draw_stub.c), also
used when chain_draw.c is missing.

    py scripts/build_mixer_ui.py [--write] [--stub]

TI_CGT = the CGT folder (default: ~/Downloads/ti-cgt-c6000_8.5.0.LTS).
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIX = ROOT / "asm/mixer"
YAML = ROOT / "patches/mixer-m2.yaml"
CGT = Path(os.environ.get("TI_CGT", Path.home() / "Downloads/ti-cgt-c6000_8.5.0.LTS"))
C_ADDR, C_END = 0xC00F8000, 0xC0106DC0         # MOD code area, record 50 (R50, chain.h) above
FAR_ADDR = 0xC00F7000                           # the C's zeroed variables (.far), after mixer.S, below C_ADDR
PERF = ROOT / "asm/perform"
CL = ["-mv6740", "--abi=eabi", "-q"]


def available() -> bool:
    return (CGT / "bin/cl6x.exe").is_file() or (CGT / "bin/cl6x").is_file()


def _run(args, cwd):
    subprocess.run([str(CGT / "bin/cl6x")] + args, check=True, cwd=cwd)


def _alloc_sections(path):
    """(addr, bytes) of every allocated ELF section, NOBITS as zeros."""
    d = Path(path).read_bytes()
    shoff, = struct.unpack_from("<I", d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)
    secs = [struct.unpack_from("<IIIIIIIIII", d, shoff + i * shentsize) for i in range(shnum)]
    strtab = secs[shstrndx][4]
    out = []
    for name, typ, flags, addr, off, size, *_ in secs:
        if flags & 2 and size:                  # SHF_ALLOC
            nm = d[strtab + name:].split(b"\0")[0].decode()
            out.append((addr, nm, bytes(size) if typ == 8 else d[off:off + size]))
    return sorted(out)


def _image(elf, addr, secs=None):
    secs = secs if secs is not None else _alloc_sections(elf)
    end = max(a + len(b) for a, _, b in secs)
    img = bytearray(end - addr)
    for a, _, b in secs:
        assert a >= addr, hex(a)
        img[a - addr:a - addr + len(b)] = b
    return bytes(img), secs


def assemble(src: Path, addr: int) -> bytes:
    """mixer.S (GNU syntax, .equ) with the TI assembler, whole fetch packets as zoomms.asm."""
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp, "a.asm")
        asm.write_text(re.sub(r"(?m)^\s+\.equ\s+(\w+),\s*", r"\1 .set ", src.read_text()))
        Path(tmp, "a.cmd").write_text(f"SECTIONS {{ .text: load = 0x{addr:08X} }}\n")
        _run(CL + [f"-I{src.parent}", "--asm_file=a.asm", "-c"], tmp)
        _run(CL + ["-z", "a.obj", "a.cmd", "-o", "a.out", "--unused_section_elimination=off"], tmp)
        code, _ = _image(Path(tmp, "a.out"), addr)
    while code.endswith(b"\0" * 4):
        code = code[:-4]
    return code + b"\0" * (-(addr + len(code)) % 32)


def build_c(stub: bool = False, listing: list | None = None) -> bytes:
    """The C section: vectors first, then code and data; no RTS, no B14."""
    draw = MIX / "chain_draw.c"
    if stub or not draw.is_file():
        draw = MIX / "chain_draw_stub.c"
    srcs = [MIX / "chain_vec.asm", MIX / "chain_keys.c", draw, MIX / "pedal_in.c",
            MIX / "engine.c", MIX / "pages.c", PERF / "perform_engine.c", PERF / "perform_store.c"]
    ui = [PERF / "perform_keys.c", PERF / "perform_draw.c"]
    srcs += ui if not stub and all(f.is_file() for f in ui) else [PERF / "perform_ui_stub.c"]
    with tempfile.TemporaryDirectory() as tmp:
        # UI code for space (-ms0; push / pop without RTS helpers), the audio path for speed
        fast = [s for s in srcs if s.name in ("engine.c", "perform_engine.c")]
        for group, opt in ((fast, []), ([s for s in srcs if s not in fast], ["-ms0", "--disable_push_pop"])):
            _run(CL + ["-O2", *opt, "--mem_model:data=far", "--mem_model:const=far", f"-I{MIX}", f"-I{PERF}", "-c"]
                 + [str(s) for s in group], tmp)
        objs = [s.stem + ".obj" for s in srcs]
        Path(tmp, "l.cmd").write_text(
            f"SECTIONS {{ GROUP: load = 0x{C_ADDR:08X} {{ .vectors .text .const .switch .fardata .neardata .rodata }}\n"
            f"  GROUP: load = 0x{FAR_ADDR:08X} {{ .far .bss }} }}\n")
        # no library: an RTS helper call (division, struct copy...) fails the link
        _run(CL + ["-z", *objs, "l.cmd", "-o", "c.out", "--ram_model", "--entry_point=chain_key",
                   "--unused_section_elimination=off", "--warn_sections"], tmp)
        secs = _alloc_sections(Path(tmp, "c.out"))
        far = [s for s in secs if s[0] < C_ADDR]
        img, _ = _image(None, C_ADDR, [s for s in secs if s[0] >= C_ADDR])
        dis = subprocess.run([str(CGT / "bin/dis6x"), "c.out"], cwd=tmp, check=True,
                             capture_output=True, text=True).stdout
    names = {n for _, n, _ in secs}
    assert names <= {".vectors", ".text", ".const", ".switch", ".fardata", ".far", ".bss", ".neardata", ".rodata"}, names
    assert not re.search(r"\bB14\b", dis), "the C must not use B14 (the OS's data pointer)"
    assert C_ADDR + len(img) <= C_END, hex(C_ADDR + len(img))
    assert all(FAR_ADDR <= a and a + len(b) <= C_ADDR for a, _, b in far), far
    global FAR_LEN
    FAR_LEN = max((a + len(b) for a, _, b in far), default=FAR_ADDR) - FAR_ADDR
    if listing is not None:
        listing.append(dis)
    return img + b"\0" * (-(C_ADDR + len(img)) % 32)


def _hex_lines(code: bytes) -> str:
    h = code.hex()
    return "".join(f"      {h[i:i + 64]}\n" for i in range(0, len(h), 64))


def main(argv):
    sys.path.insert(0, str(ROOT))
    from zoomms import patcher
    builds = {"asm/mixer/mixer.S": lambda a: assemble(MIX / "mixer.S", a),
              "asm/mixer/chain_keys.c": lambda a: build_c("--stub" in argv),
              "asm/mixer/far": lambda a: bytes(-(-FAR_LEN // 32) * 32)}   # after chain_keys.c in the yaml
    text, ok = YAML.read_text(), True
    for sec in patcher.load(YAML)["section"]:
        if sec["source"] not in builds:   # asm/master/master.c: scripts/build_master_ui.py
            continue
        code = builds[sec["source"]](sec["addr"])
        same = bytes.fromhex("".join(sec["data"].split())) == code
        print(sec["source"], f"0x{sec['addr']:08X}-0x{sec['addr'] + len(code):08X}", "OK" if same else "DIFF")
        ok &= same
        pat = re.compile(rf"(source: {re.escape(sec['source'])}\n(?:    #.*\n)*    data: >-\n)(?:      [0-9a-f]+\n)*")
        text = pat.sub(lambda m: m.group(1) + _hex_lines(code), text, count=1)
    if "--write" in argv and not ok:
        YAML.write_text(text)
        print("written")
    return 0 if ok or "--write" in argv else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
