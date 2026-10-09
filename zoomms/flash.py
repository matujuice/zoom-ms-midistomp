"""The official updater's flash script, and building a modified updater.

The updater .exe (observed for MS-50G v3.10, MS-60B v2.10, MS-70CDR v2.10)
holds a table of 16-byte steps it sends to the pedal's bootloader over USB
MIDI, in order:

    type, flash address, length, resource id      type 1 = erase, 2 = write

MS-50G v3.10:
    erase 0x0EF000 +0x1000      last sector of the OS area (trailer), first
    erase 0x000000 +0x40000     write BIN/136 bootloader
    erase 0x3FD000 +0x3000      write BIN/133
    erase 0x040000 +0xB0000     write BIN/129 main OS, last

MS-60B / MS-70CDR also write BIN/137 (effects file system) at 0x0F0000.

Erasing the OS trailer first and writing the OS last looks like how the
bootloader knows an update was interrupted (inferred). The stock updater
rewrites the bootloader on every update, which is the one step that could
brick a pedal beyond USB recovery if interrupted. build_updater() therefore
turns the bootloader steps (and BIN/133) into no-ops: the loop in the updater
skips any step whose type is not 1 or 2.

BIN/133 starts with the boot logo (128x64, page format: one byte = 8 vertical
pixels, LSB on top, 128 bytes per page). A build that changes it keeps the
BIN/133 steps, like the stock updater; the bootloader steps stay skipped.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from . import parts

ERASE, WRITE, SKIP = 1, 2, 0
STEP = 16
OS_WRITE = struct.pack("<4I", WRITE, 0x40000, 0xB0000, 129)


@dataclass
class Step:
    offset: int  # file offset of this step in the .exe
    kind: int
    addr: int
    length: int
    resource: int

    def describe(self) -> str:
        name = {ERASE: "erase", WRITE: "write", SKIP: "skip"}.get(self.kind, f"type{self.kind}")
        res = f" BIN/{self.resource}" if self.kind == WRITE else ""
        return f"{name:<5} 0x{self.addr:06X} +0x{self.length:X}{res}"


def find_script(exe: bytes) -> list[Step]:
    pos = exe.find(OS_WRITE)
    if pos < 0:
        raise ValueError("flash script not found (no 'write main OS' step)")
    start = pos
    while start >= STEP:
        prev = struct.unpack_from("<4I", exe, start - STEP)
        if prev[0] not in (ERASE, WRITE, SKIP) or prev[1] >= 0x400000 or prev[2] > 0x400000:
            break
        start -= STEP
    steps, off = [], start
    while off + STEP <= len(exe):
        k, a, n, r = struct.unpack_from("<4I", exe, off)
        if k not in (ERASE, WRITE, SKIP) or a >= 0x400000 or n > 0x400000:
            break
        steps.append(Step(off, k, a, n, r))
        off += STEP
    return steps


def boot_steps(steps: list[Step], keep_133: bool = False) -> list[Step]:
    """Steps touching the bootloader area (and BIN/133 unless keep_133)."""
    out = []
    for s in steps:
        if s.addr < 0x40000:
            out.append(s)
        elif not keep_133 and s.addr == 0x3FD000:
            out.append(s)
    return out


def build_updater(exe_path: str, new_os: bytes | None = None, skip_boot: bool = True,
                  new_133: bytes | None = None) -> bytes:
    """new_133: modified BIN/133 (boot logo); its erase/write steps then stay on."""
    exe = bytearray(open(exe_path, "rb").read())
    for rid, new in ((129, new_os), (133, new_133)):
        if new is None:
            continue
        part = next(p for p in parts.find_parts(exe_path) if p.resource_id == rid)
        if len(new) != part.size:
            raise ValueError(f"new BIN/{rid} is {len(new)} B, resource slot is {part.size} B")
        exe[part.offset:part.offset + part.size] = new
    if skip_boot:
        for s in boot_steps(find_script(bytes(exe)), keep_133=new_133 is not None):
            struct.pack_into("<I", exe, s.offset, SKIP)
    return _unsign(bytes(exe))


def _unsign(exe: bytes) -> bytes:
    """Drop Zoom's Authenticode signature (no longer valid once modified) and
    fix the PE checksum, so Windows sees a plain unsigned program rather than
    a tampered signed one."""
    import pefile

    pe = pefile.PE(data=exe)
    cert = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]]
    if cert.Size:
        start = cert.VirtualAddress  # a file offset for this directory
        cert.VirtualAddress = cert.Size = 0
        pe.__data__ = pe.write()[:start]
        pe = pefile.PE(data=pe.__data__)
    pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()
    return bytes(pe.write())
