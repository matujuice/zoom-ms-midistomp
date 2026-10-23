"""Build the GRDLOOP status bar section of patches/looper.yaml with TI CGT 8.5
(asm/looper/lbox_vec.asm + lbox.c, linked at 0xC00F5400). Compares it with the
yaml, or --write replaces the yaml hex.

    py scripts/build_looper_ui.py [--write]
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mixer_ui import CGT, CL, ROOT, _hex_lines, _image, _run, available  # noqa: E402,F401

LOOP = ROOT / "asm/looper"
YAML = ROOT / "patches/looper.yaml"
ADDR, END = 0xC00F5400, 0xC00F6000            # after m0-probe, before mixer.S
SOURCE = "asm/looper/lbox.c"


def build(srcs=(LOOP / "lbox_vec.asm", LOOP / "lbox.c"), addr=ADDR, end=END, entry="lbox_draw", opt=("--opt_for_speed=2",)) -> bytes:
    """Compile and link srcs (the vectors first) at addr; the image, padded to 32 B."""
    ADDR, END = addr, end
    objs = [Path(s).stem + ".obj" for s in srcs]
    with tempfile.TemporaryDirectory() as tmp:
        _run(CL + ["-O2", *opt, "--mem_model:data=far", "--mem_model:const=far", "-c"] + [str(s) for s in srcs], tmp)
        Path(tmp, "l.cmd").write_text(
            f"SECTIONS {{ GROUP: load = 0x{ADDR:08X} {{ .vectors .text .const .switch .fardata .far .bss .neardata .rodata }} }}\n")
        # no library: an RTS helper call (division...) fails the link
        _run(CL + ["-z"] + objs + ["l.cmd", "-o", "c.out", "--ram_model",
                   f"--entry_point={entry}", "--unused_section_elimination=off", "--warn_sections"], tmp)
        img, secs = _image(Path(tmp, "c.out"), ADDR)
        # the C objects only: data in .vectors (stamps, strings) disassembles as junk
        dis = "".join(subprocess.run([str(CGT / "bin/dis6x"), o], cwd=tmp, check=True,
                                     capture_output=True, text=True).stdout
                      for o, s in zip(objs, srcs) if Path(s).suffix == ".c")
    assert not re.search(r"\bB14\b", dis), "the C must not use B14 (the OS's data pointer)"
    img += b"\0" * (-(ADDR + len(img)) % 32)
    assert ADDR + len(img) <= END, hex(ADDR + len(img))
    return img


def main(argv, code=None, yaml=YAML, source=SOURCE, addr=ADDR):
    """Compare the yaml hex under `source: <source>` with code (default: the looper's)."""
    YAML, SOURCE, ADDR = yaml, source, addr
    code = build() if code is None else code
    text = YAML.read_text()
    pat = re.compile(rf"(source: {re.escape(SOURCE)}\n(?:    #.*\n)*    data: >-\n)((?:      [0-9a-f]+\n)*)")
    m = pat.search(text)
    same = bool(m) and bytes.fromhex("".join(m.group(2).split())) == code
    print(SOURCE, f"0x{ADDR:08X}-0x{ADDR + len(code):08X}", "OK" if same else "DIFF")
    if "--write" in argv and m and not same:
        YAML.write_text(text[:m.start(2)] + _hex_lines(code) + text[m.end(2):])
        print("written")
    return 0 if same or "--write" in argv else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
