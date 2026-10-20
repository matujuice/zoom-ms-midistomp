"""Zoom's Mac updater app, and building a modified one.

The Mac updater (observed for MS-50G v3.10 and MS-70CDR v2.10) is an x86_64
Cocoa app that keeps the firmware as plain files in Contents/Resources,
byte-identical to the Windows updater's resources:

    Main.bin    BIN/129  main OS
    FS.bin      BIN/137  effects file system (written by the MS-70CDR script only)
    Preset.bin  BIN/133  boot logo block
    boot.bin    BIN/136  bootloader

`-[MainWindow ReadUpdateBin:]` refuses a file whose MD5 does not match a
table of hex strings in the executable (`_MD5Tbl`, same order as `_BinName`).

`-[MainWindow DoUpdate]` walks `_RomProcedure`, the same script as the Windows
updater (see flash.py: 7 steps, 9 with the MS-70CDR's FS.bin) but with its own
step types:

    type, flash address, length, file index   type 0 = erase, 1 = write

A write with length 0 sends the whole file. Any other type is skipped (the
loop only acts on 0 and 1), which is how build_app() turns off the steps
flash.boot_steps() names: bootloader, effects file system and Preset.bin.

The executable is code-signed, so a modified app has to be re-signed on the
Mac (`xattr -cr <app> && codesign --force --deep --sign - <app>`) before
macOS will run it.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from . import flash

ERASE, WRITE, SKIP = 0, 1, 2
STEP = 16
NO_FILE = 255
TEXT_VMADDR = 0x100000000
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
# MS-70CDR v2.10: the same plus the effects file system before the main OS.
SCRIPT_70CDR = SCRIPT[:5] + [
    (ERASE, 0x0F0000, 0x2C7000, NO_FILE),
    (WRITE, 0x0F0000, 0x2C7000, 1),       # FS.bin
] + SCRIPT[5:]
SCRIPTS = [SCRIPT, SCRIPT_70CDR]


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
    """The steps of _RomProcedure, checked against one of SCRIPTS (types may be SKIP)."""
    pos = exe.find(OS_ERASE)
    if pos < 0:
        raise ValueError("flash script not found (no 'erase main OS' step)")
    if exe.find(OS_ERASE, pos + 1) >= 0:
        raise ValueError("flash script not where expected")
    for script in SCRIPTS:
        start = pos - (len(script) - 2) * STEP
        if start < 0 or start + len(script) * STEP > len(exe):
            continue
        steps = [Step(start + i * STEP, *struct.unpack_from("<4I", exe, start + i * STEP)) for i in range(len(script))]
        if all((s.addr, s.length, s.file) == (a, n, f) and s.kind in (k, SKIP)
               for s, (k, a, n, f) in zip(steps, script)):
            return steps
    raise ValueError(f"unexpected flash script before the 'erase main OS' step at 0x{pos:X}")


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


TITLE = re.compile(rb"\0(ZOOM [ -~]{1,40} Updater)\0")


def find_title(exe: bytes) -> str:
    """Zoom's window title, e.g. "ZOOM MS-70CDR v2.10 Updater" (not taken from
    the .app name, which the user may have changed)."""
    found = TITLE.findall(exe)
    if len(found) != 1:
        raise ValueError(f"window title not found exactly once ({len(found)} candidates)")
    return found[0].decode()


def set_title(exe: bytearray, old: str, new: str) -> None:
    """Change the window title, a constant CFString whose characters are a C
    string in __TEXT,__cstring: {isa, flags, pointer, length} in __DATA. The
    new title is written over the old one, so it can't be longer."""
    if not new.isascii() or not new.isprintable():
        raise ValueError(f"title {new!r} must be plain ASCII")
    old_b, new_b = old.encode("ascii"), new.encode("ascii")
    if len(new_b) > len(old_b):
        raise ValueError(f"title {new!r} is longer than {old!r} ({len(old_b)} characters)")
    at = exe.find(b"\0" + old_b + b"\0") + 1
    if at <= 0 or exe.count(b"\0" + old_b + b"\0") != 1:
        raise ValueError(f"title {old!r} not found exactly once")
    ref = struct.pack("<QQ", TEXT_VMADDR + at, len(old_b))  # __TEXT has file offset 0
    if exe.count(ref) != 1:
        raise ValueError(f"no CFString for title {old!r}")
    exe[at:at + len(old_b)] = new_b + bytes(len(old_b) - len(new_b))
    struct.pack_into("<Q", exe, exe.find(ref) + 8, len(new_b))


def build_app(stock_app: str | Path, out_app: str | Path, new_os: bytes | None = None,
              new_133: bytes | None = None, skip_boot: bool = True, title: str | None = None) -> list[Step]:
    """Copy stock_app to out_app with new Main.bin / Preset.bin, matching MD5
    table entries and the steps flash.boot_steps() names set to skip
    (bootloader, effects file system, and Preset.bin unless new_133 is given).
    The window title, Zoom's app name, becomes title if given. Returns the new
    flash script."""
    stock_app, out_app = Path(stock_app), Path(out_app)
    if out_app.exists():
        raise FileExistsError(f"{out_app} already exists")
    exe = bytearray(executable(stock_app).read_bytes())
    if title is not None:
        set_title(exe, find_title(bytes(exe)), title)
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
        for s in flash.boot_steps(steps, keep_133=new_133 is not None):
            struct.pack_into("<I", exe, s.offset, SKIP)
    if len(steps) == len(SCRIPT_70CDR) and not accept_models(exe):
        raise ValueError("model check not found: the app would refuse MS-50G and MS-60B pedals")

    shutil.copytree(stock_app, out_app, symlinks=True)
    executable(out_app).write_bytes(bytes(exe))
    for name, data in replace.items():
        (resources(out_app) / name).write_bytes(data)
    return find_script(bytes(exe))


# The updater's model check (MS-70CDR v2.10, block in -[MainWindow SendIdReq]):
# the pedal's model byte (_SysEX4ByteID, 0x58 on every v1.0/v1.1 pedal) must be
# in _kTargetDeviceIDs, two int32 {0x57, 0x61}, else "Illegal device connected".
#   cmpq $2,-0x18(%rbp); jae; leaq _kTargetDeviceIDs(%rip),%rax; movq -0x18(%rbp),%rcx
#   shlq $2,%rcx; addq %rcx,%rax; movl (%rax),%edx; movl _SysEX4ByteID(%rip),%esi
# A double follows the list, so it cannot grow in place. Instead the list is
# read as bytes (movzbl (%rax,%rcx),%edx + 5-byte nop), its 8 bytes hold
# flash.MODELS, and the loop bound goes from 2 to 4.
MODEL_LOOP = (bytes.fromhex("48837de8020f83"), bytes.fromhex("488d05"),
              bytes.fromhex("488b4de848c1e1024801c88b108b35"))
MODEL_LOAD = bytes.fromhex("488b4de8" "0fb61408" "0f1f440000")  # movq; movzbl (%rax,%rcx),%edx; 5-byte nop


def _find_model_loop(exe: bytes) -> int:
    at = exe.find(MODEL_LOOP[0])
    while at >= 0:
        lea = at + len(MODEL_LOOP[0]) + 4
        if exe[lea:lea + 3] == MODEL_LOOP[1] and exe[lea + 7:lea + 7 + len(MODEL_LOOP[2])] == MODEL_LOOP[2]:
            return at
        at = exe.find(MODEL_LOOP[0], at + 1)
    return -1


def accept_models(exe: bytearray) -> bool:
    """Let the updater flash any pedal in flash.MODELS. False if the check is
    not the one above (the MS-50G app has a different one and needs no change)."""
    at = _find_model_loop(bytes(exe))
    if at < 0:
        return False
    lea = at + len(MODEL_LOOP[0]) + 4
    # __TEXT has file offset 0, so a RIP-relative target in it is a file offset.
    table = lea + 7 + struct.unpack_from("<i", exe, lea + 3)[0]
    if not 0 <= table <= len(exe) - 8 or struct.unpack_from("<2I", exe, table) != (0x57, 0x61):
        return False
    exe[table:table + 8] = flash.MODELS + bytes(8 - len(flash.MODELS))
    exe[at + 4] = len(flash.MODELS)
    exe[lea + 7:lea + 7 + len(MODEL_LOAD)] = MODEL_LOAD
    return True
