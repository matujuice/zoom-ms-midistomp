import struct

from zoomms import flash


def test_find_script_and_boot_steps():
    steps = [(1, 0xEF000, 0x1000, 0), (1, 0, 0x40000, 0), (2, 0, 0x40000, 136),
             (1, 0x3FD000, 0x3000, 0), (2, 0x3FD000, 0x3000, 133),
             (1, 0x40000, 0xB0000, 0), (2, 0x40000, 0xB0000, 129)]
    exe = b"\xcc" * 64 + b"".join(struct.pack("<4I", *s) for s in steps) + b"USB Midi"
    found = flash.find_script(exe)
    assert [(s.kind, s.addr, s.length, s.resource) for s in found] == steps
    skipped = flash.boot_steps(found)
    assert [s.addr for s in skipped] == [0, 0, 0x3FD000, 0x3FD000]
    assert [s.addr for s in flash.boot_steps(found, keep_133=True)] == [0, 0]
