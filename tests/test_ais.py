import struct

from zoomms import ais


def make_ais():
    w = [ais.MAGIC, ais.NOARG_63, ais.FUNCTION_EXECUTE, (2 << 16) | 5, 0x11, 0x22,
         ais.SET, 0x20004, 0x01C14188, 5, 0,
         ais.SECTION_LOAD, 0x11800000, 6]
    data = struct.pack(f"<{len(w)}I", *w) + b"abcdef\0\0"
    return data + struct.pack("<2I", ais.JUMP_CLOSE, 0x11800000) + b"\xff" * 16


def test_parse():
    img = ais.parse(make_ais())
    assert img.entry == 0x11800000
    assert [(s.addr, s.data) for s in img.sections] == [(0x11800000, b"abcdef")]
    assert img.functions == [(5, [0x11, 0x22])]
    assert img.sets == [(0x20004, 0x01C14188, 5, 0)]


def test_elf_wrap_has_section_at_load_address():
    elf = ais.to_elf(ais.parse(make_ais()))
    assert elf[:4] == b"\x7fELF" and struct.unpack_from("<H", elf, 18)[0] == 140
    assert b"abcdef" in elf and b".s11800000" in elf
