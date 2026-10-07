"""Read-only parser for .ZDL effect modules.

Layout as documented by ZoomMultistompZDL (MIT, repeat98):

    NULL(4) | "SIZE" u32=8, u32 header_size, u32 elf_size
            | "INFO" u32=48, 48-byte payload | [BCAB/CABI extra] | TI C6000 ELF

All integers little-endian. The ELF is a TI C674x ET_DYN shared object.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

FX_TYPES = {
    1: "Dynamics", 2: "Filter", 3: "Drive", 4: "GuitarAmp", 5: "BassAmp",
    6: "Modulation", 7: "SFX", 8: "Delay", 9: "Reverb", 11: "PedalOperated",
    12: "BassDrive", 13: "BassPreamp", 15: "ExtraDLL", 20: "BassDrive", 22: "BassPreamp",
}
EM_TI_C6000 = 140


class ZdlError(ValueError):
    pass


@dataclass
class Zdl:
    version_string: str
    real_type: int
    knob_type: int
    sort_index: int
    sort_fx_type: int
    bass_flags: int
    fx_version: str
    header_size: int
    extra: bytes
    elf: bytes
    # A few stock files (e.g. MS-60B_GATE_REV) carry a stale SIZE elf_size,
    # so the ELF is taken to run to end of file and the header value is kept.
    declared_elf_size: int

    @property
    def category(self) -> str:
        return FX_TYPES.get(self.real_type, f"type{self.real_type}")

    @property
    def elf_machine(self) -> int:
        return struct.unpack_from("<H", self.elf, 18)[0]


def parse(data: bytes) -> Zdl:
    if data[:4] != b"\x00" * 4 or data[4:8] != b"SIZE":
        raise ZdlError("missing NULL prefix / SIZE block")
    size_len, header_size, elf_size = struct.unpack_from("<III", data, 8)
    if size_len != 8:
        raise ZdlError(f"unexpected SIZE length {size_len}")
    if data[20:24] != b"INFO" or struct.unpack_from("<I", data, 24)[0] != 48:
        raise ZdlError("missing or unsupported INFO block")
    info = data[28:76]
    elf_start = 20 + header_size
    if elf_start < 76:
        raise ZdlError(f"header_size {header_size} too small")
    elf = data[elf_start:]
    if elf[:4] != b"\x7fELF":
        raise ZdlError("ELF magic not found")
    return Zdl(
        version_string=info[:32].split(b"\x00", 1)[0].decode("latin-1"),
        real_type=info[32], knob_type=info[34], sort_index=info[36],
        bass_flags=info[38], sort_fx_type=info[39],
        fx_version=info[40:48].split(b"\x00", 1)[0].decode("latin-1"),
        header_size=header_size, extra=data[76:elf_start], elf=elf,
        declared_elf_size=elf_size,
    )


def load(path: str | Path) -> Zdl:
    return parse(Path(path).read_bytes())
