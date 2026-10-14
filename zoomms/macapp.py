"""Zoom's Mac updater app, and building a modified one.

The Mac updater (observed for MS-50G v3.10) is an x86_64 Cocoa app that keeps
the firmware as plain files in Contents/Resources, byte-identical to the
Windows updater's resources:

    Main.bin    BIN/129  main OS
    FS.bin      BIN/137  effects file system (not written by the MS-50G script)
    Preset.bin  BIN/133  boot logo block
    boot.bin    BIN/136  bootloader

`-[MainWindow ReadUpdateBin:]` refuses a file whose MD5 does not match a
table of hex strings in the executable (`_MD5Tbl`, same order as `_BinName`).

`-[MainWindow DoUpdate]` walks `_RomProcedure`, the same 7-step script as the
Windows updater (see flash.py) but with its own step types:

    type, flash address, length, file index   type 0 = erase, 1 = write

A write with length 0 sends the whole file. Any other type is skipped (the
loop only acts on 0 and 1), which is how build_app() turns off the bootloader
steps.

The executable is code-signed, so a modified app has to be re-signed on the
Mac (`codesign --force --deep --sign - <app>`) before macOS will run it.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

ERASE, WRITE, SKIP = 0, 1, 2
STEP = 16
NO_FILE = 255
OS_ERASE = struct.pack("<4I", ERASE, 0x40000, 0xB0000, NO_FILE)
BIN_NAMES = ["Main", "FS", "Preset", "boot"]  # index = file index in a write step
FILE_FOR_RESOURCE = {129: "Main.bin", 133: "Preset.bin"}
# MS-50G v3.10 _RomProcedure, as shipped.
SCRIPT = [
    (ERASE, 0x0EF000, 0x1000, NO_FILE),   # OS trailer
    (ERASE, 0x000000, 0x40000, NO_FILE),  # bootloader
    (WRITE, 0x000000, 0x40000, 3),        # boot.bin
    (ERASE, 0x3FD000, 0x3000, NO_FILE),
    (WRITE, 0x3FD000, 0x3000, 2),         # Preset.bin
    (ERASE, 0x040000, 0xB0000, NO_FILE),  # main OS
    (WRITE, 0x040000, 0, 0),              # Main.bin, whole file
]


@dataclass
class Step:
    offset: int  # file offset of this step in the executable
    kind: int
    addr: int
    length: int
    file: int

    def describe(self) -> str:
        name = {ERASE: "erase", WRITE: "write", SKIP: "skip"}.get(self.kind, f"type{self.kind}")
        what = ""
        if self.kind == WRITE and self.file < len(BIN_NAMES):
            what = f" {BIN_NAMES[self.file]}.bin"
        length = f"+0x{self.length:X}" if self.length else "+file"
        return f"{name:<5} 0x{self.addr:06X} {length}{what}"


def executable(app: Path) -> Path:
    return app / "Contents" / "MacOS" / "EFX Updater"


def resources(app: Path) -> Path:
    return app / "Contents" / "Resources"


def find_script(exe: bytes) -> list[Step]:
    """The 7 steps of _RomProcedure, checked against SCRIPT (types may be SKIP)."""
    pos = exe.find(OS_ERASE)
    if pos < 0:
        raise ValueError("flash script not found (no 'erase main OS' step)")
    start = pos - 5 * STEP
    if start < 0 or exe.find(OS_ERASE, pos + 1) >= 0:
        raise ValueError("flash script not where expected")
    steps = [Step(start + i * STEP, *struct.unpack_from("<4I", exe, start + i * STEP)) for i in range(len(SCRIPT))]
    for s, (k, a, n, f) in zip(steps, SCRIPT):
        if (s.addr, s.length, s.file) != (a, n, f) or s.kind not in (k, SKIP):
            raise ValueError(f"unexpected flash step at 0x{s.offset:X}: {s.describe()}")
    return steps


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def build_app(stock_app: str | Path, out_app: str | Path, new_os: bytes | None = None,
              new_133: bytes | None = None, skip_boot: bool = True) -> list[Step]:
    """Copy stock_app to out_app with new Main.bin / Preset.bin, matching MD5
    table entries and the bootloader steps (and Preset.bin's, unless new_133
    is given) set to skip. Returns the new flash script."""
    stock_app, out_app = Path(stock_app), Path(out_app)
    if out_app.exists():
        raise FileExistsError(f"{out_app} already exists")
    exe = bytearray(executable(stock_app).read_bytes())
    steps = find_script(bytes(exe))
    for name in BIN_NAMES:
        if md5_hex((resources(stock_app) / f"{name}.bin").read_bytes()).encode() not in exe:
            raise ValueError(f"{name}.bin does not match the updater's MD5 table")

    replace = {}
    for rid, new in ((129, new_os), (133, new_133)):
        if new is None:
            continue
        name = FILE_FOR_RESOURCE[rid]
        old = (resources(stock_app) / name).read_bytes()
        if len(new) != len(old):
            raise ValueError(f"new {name} is {len(new)} B, stock is {len(old)} B")
        old_md5 = md5_hex(old).encode()
        if exe.count(old_md5) != 1:
            raise ValueError(f"MD5 of stock {name} not found exactly once in the executable")
        exe[exe.find(old_md5):exe.find(old_md5) + 32] = md5_hex(new).encode()
        replace[name] = new

    if skip_boot:
        for s in steps:
            if s.addr < 0x40000 or (new_133 is None and s.addr == 0x3FD000):
                struct.pack_into("<I", exe, s.offset, SKIP)

    shutil.copytree(stock_app, out_app, symlinks=True)
    executable(out_app).write_bytes(bytes(exe))
    for name, data in replace.items():
        (resources(out_app) / name).write_bytes(data)
    return find_script(bytes(exe))
