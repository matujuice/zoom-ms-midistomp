"""Parser for TI AIS (Application Image Script) boot images.

AIS is the boot-script format read by the ROM bootloader of TI C674x /
OMAP-L13x parts (TI SPRAB41). The MS-series bootloader and main OS are both
AIS images (see parts.py). Opcodes seen in the MS-60B v2.10 main OS:

    0x58535901  section load      addr, size, data (padded to 4 bytes)
    0x58535906  jump and close    entry point
    0x58535907  set               type, addr, value, delay (register write)
    0x5853590D  function execute  (nargs << 16 | index), args...
    0x58535963  no arguments, meaning not confirmed
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = 0x41504954
SECTION_LOAD = 0x58535901
REQUEST_CRC = 0x58535902
ENABLE_CRC = 0x58535903
DISABLE_CRC = 0x58535904
JUMP = 0x58535905
JUMP_CLOSE = 0x58535906
SET = 0x58535907
SECTION_FILL = 0x5853590A
FUNCTION_EXECUTE = 0x5853590D
NOARG_63 = 0x58535963


class AisError(ValueError):
    pass


@dataclass
class Section:
    addr: int
    data: bytes


@dataclass
class AisImage:
    sections: list[Section] = field(default_factory=list)
    fills: list[tuple[int, int, int, int]] = field(default_factory=list)
    sets: list[tuple[int, int, int, int]] = field(default_factory=list)
    functions: list[tuple[int, list[int]]] = field(default_factory=list)
    entry: int | None = None
    end_offset: int = 0
    log: list[str] = field(default_factory=list)


def parse(data: bytes) -> AisImage:
    def word(o: int) -> int:
        if o + 4 > len(data):
            raise AisError(f"truncated at 0x{o:X}")
        return struct.unpack_from("<I", data, o)[0]

    if word(0) != MAGIC:
        raise AisError("not an AIS image")
    img, o = AisImage(), 4
    while True:
        op = word(o)
        o += 4
        if op == SECTION_LOAD:
            addr, size = word(o), word(o + 4)
            img.sections.append(Section(addr, data[o + 8:o + 8 + size]))
            img.log.append(f"load 0x{addr:08X} +0x{size:X}")
            o += 8 + ((size + 3) & ~3)
        elif op == SECTION_FILL:
            img.fills.append(tuple(word(o + 4 * i) for i in range(4)))
            img.log.append("fill 0x%08X +0x%X type %d pattern 0x%08X" % img.fills[-1])
            o += 16
        elif op == SET:
            img.sets.append(tuple(word(o + 4 * i) for i in range(4)))
            img.log.append("set type 0x%X [0x%08X] = 0x%08X delay %d" % img.sets[-1])
            o += 16
        elif op == FUNCTION_EXECUTE:
            hdr = word(o)
            n, idx = hdr >> 16, hdr & 0xFFFF
            args = [word(o + 4 + 4 * i) for i in range(n)]
            img.functions.append((idx, args))
            img.log.append(f"function {idx}(" + ", ".join(f"0x{a:X}" for a in args) + ")")
            o += 4 + 4 * n
        elif op == REQUEST_CRC:
            img.log.append(f"crc 0x{word(o):08X} seek {word(o + 4)}")
            o += 8
        elif op in (ENABLE_CRC, DISABLE_CRC, NOARG_63):
            img.log.append(f"op 0x{op:08X}")
        elif op in (JUMP, JUMP_CLOSE):
            img.entry = word(o)
            img.log.append(f"{'jump and close' if op == JUMP_CLOSE else 'jump'} 0x{img.entry:08X}")
            o += 4
            if op == JUMP_CLOSE:
                img.end_offset = o
                return img
        else:
            raise AisError(f"unknown opcode 0x{op:08X} at 0x{o - 4:X}")


def to_elf(img: AisImage) -> bytes:
    """Wrap the loaded sections in a minimal little-endian TI C6000 ELF so
    GNU binutils (tic6x-elf-objdump) can disassemble them at their real
    addresses."""
    secs = sorted(img.sections, key=lambda s: s.addr)
    names = b"\0" + b"".join(f".s{s.addr:08x}\0".encode() for s in secs) + b".shstrtab\0"
    ehsize, phent, shent = 0x34, 0x20, 0x28
    off = ehsize + phent * len(secs)
    body, offsets = bytearray(), []
    for s in secs:
        offsets.append(off + len(body))
        body += s.data + b"\0" * (-len(s.data) % 4)
    shstr_off = off + len(body)
    sh_off = shstr_off + len(names) + (-len(names) % 4)
    nsh = len(secs) + 2
    out = bytearray(sh_off + shent * nsh)
    out[:16] = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    struct.pack_into("<HHIIIIIHHHHHH", out, 16, 2, 140, 1, img.entry or 0, ehsize, sh_off,
                     0, ehsize, phent, len(secs), shent, nsh, nsh - 1)
    for i, (s, so) in enumerate(zip(secs, offsets)):
        struct.pack_into("<8I", out, ehsize + i * phent, 1, so, s.addr, s.addr,
                         len(s.data), len(s.data), 7, 4)
    out[off:off + len(body)] = body
    out[shstr_off:shstr_off + len(names)] = names
    name_off = 1
    for i, (s, so) in enumerate(zip(secs, offsets), start=1):
        struct.pack_into("<10I", out, sh_off + i * shent, name_off, 1, 6, s.addr, so,
                         len(s.data), 0, 0, 4, 0)
        name_off += len(f".s{s.addr:08x}") + 1
    struct.pack_into("<10I", out, sh_off + (nsh - 1) * shent, name_off, 3, 0, 0,
                     shstr_off, len(names), 0, 0, 1, 0)
    return bytes(out)
