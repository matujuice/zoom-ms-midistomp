"""Assemble our C674x code (asm/*.S) with GNU binutils (target tic6x-elf,
see scripts/build-c6x-binutils.sh) into raw bytes linked at a fixed address.

Only needed when changing assembly: patch files carry the assembled bytes, so
building an updater does not need binutils.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

PREFIX = os.environ.get("C6X_PREFIX", "/opt/c6x/bin/tic6x-elf-")


def available() -> bool:
    return Path(PREFIX + "as").exists()


def assemble(src: str | Path, addr: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        obj, elf, out, ld = (os.path.join(tmp, n) for n in ("a.o", "a.elf", "a.bin", "a.ld"))
        Path(ld).write_text(f"SECTIONS {{ . = 0x{addr:08X}; .text : {{ *(.text) }} /DISCARD/ : {{ *(*) }} }}\n")
        subprocess.run([PREFIX + "as", "-mlittle-endian", "-march=c674x", "-o", obj, str(src)], check=True)
        subprocess.run([PREFIX + "ld", "-EL", "-T", ld, "-e", hex(addr), "-o", elf, obj], check=True)
        subprocess.run([PREFIX + "objcopy", "-O", "binary", "-j", ".text", elf, out], check=True)
        code = Path(out).read_bytes()
    # The assembler pads the section to a whole fetch packet with zero words
    # (single-cycle nops). Our code always ends in a branch plus its delay
    # slots, so that padding is never executed: drop it.
    while code.endswith(b"\0" * 4):
        code = code[:-4]
    return code
