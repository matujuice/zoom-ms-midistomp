"""Locate the firmware parts embedded as BIN resources in an official updater.

Observed in the MS-50G v3.10, MS-60B v2.10 and MS-70CDR v2.10 updaters (all
three executables are the same size and use the same resource ids):

    BIN/136  256 KiB  bootloader, TI AIS image   identical on all three models
    BIN/129  704 KiB  main OS, TI AIS image      per model
    BIN/133   12 KiB  unknown, bitmap-like data  per model
    BIN/137  2.8 MiB  flash file system (effects) per model, see updater.py

AIS (magic 0x41504954) is the boot-script format read by the ROM bootloader of
TI C674x / OMAP-L13x parts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AIS_MAGIC = b"\x54\x49\x50\x41"
ROLES = {129: "main OS", 133: "data 133", 136: "bootloader", 137: "file system"}


@dataclass
class Part:
    resource_id: int
    role: str
    offset: int
    size: int
    kind: str


def _kind(head: bytes) -> str:
    if head.startswith(AIS_MAGIC):
        return "TI AIS image"
    if head.startswith(bytes.fromhex("55AA00010400")):
        return "flash file system"
    return "data"


def find_parts(path: str | Path) -> list[Part]:
    import pefile

    pe = pefile.PE(str(path))
    data = pe.__data__
    parts = []
    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        return []
    for rtype in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if str(rtype.name) != "BIN":
            continue
        for entry in rtype.directory.entries:
            for lang in entry.directory.entries:
                s = lang.data.struct
                off = pe.get_offset_from_rva(s.OffsetToData)
                parts.append(Part(entry.id, ROLES.get(entry.id, "unknown"), off, s.Size,
                                  _kind(bytes(data[off:off + 6]))))
    return sorted(parts, key=lambda p: p.offset)


def read_part(path: str | Path, part: Part) -> bytes:
    with open(path, "rb") as f:
        f.seek(part.offset)
        return f.read(part.size)
