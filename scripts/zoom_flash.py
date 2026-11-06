"""Flash a Zoom updater's main OS over USB MIDI, the way Zoom's updater does (docs/dev/flash-protocol.md).

For protocol tests, not for users: the release updater stays the way to flash.

  py scripts/zoom_flash.py check UPDATER.exe flash-log.txt      # our messages vs a capture log (offline)
  py scripts/zoom_flash.py flash UPDATER.exe [--bad-crc N]      # pedal must be in update mode

--bad-crc N sends OS chunk N first with a wrong CRC (same data), prints what the pedal answers,
then sends it again correctly and carries on. The data is unchanged, so even if the pedal writes
the bad message, the good one writes the same bytes. Only the main OS is written (no bootloader,
no file system, no logo), so a failed run is fixed by running the release updater.
"""

from __future__ import annotations

import hashlib
import re
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoomms import parts  # noqa: E402

HEAD = bytes([0xF0, 0x52, 0x00, 0x61])
ACK = HEAD + bytes([0x00, 0x00, 0xF7])
OS_ADDR, OS_LEN, TRAILER, CHUNK = 0x040000, 0xB0000, 0x0EF000, 0x800


def num(value: int, n: int) -> bytes:
    """7-bit little-endian."""
    return bytes((value >> (7 * i)) & 0x7F for i in range(n))


def pack7(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 7):
        group = data[i:i + 7]
        out.append(sum(((b >> 7) & 1) << (6 - j) for j, b in enumerate(group)))
        out += bytes(b & 0x7F for b in group)
    return bytes(out)


def start() -> bytes:
    return HEAD + b"\x01\xF7"


def erase(addr: int, length: int) -> bytes:
    return HEAD + b"\x0A" + num(addr, 5) + num(length, 5) + b"\xF7"


def write(addr: int, data: bytes, bad_crc: bool = False) -> bytes:
    assert len(data) == CHUNK
    crc = zlib.crc32(data) ^ 0xFFFFFFFF
    if bad_crc:
        crc ^= 1
    return HEAD + b"\x02" + num(addr, 5) + num(CHUNK, 2) + pack7(data) + num(crc, 5) + b"\xF7"


def finish() -> bytes:
    return HEAD + b"\x04\xF7"


def os_image(updater: Path) -> bytes:
    part = next(p for p in parts.find_parts(updater) if p.resource_id == 129)
    data = parts.read_part(updater, part)
    assert len(data) == OS_LEN, f"BIN/129 is {len(data)} B, expected {OS_LEN}"
    return data


def os_writes(image: bytes):
    for i in range(0, OS_LEN, CHUNK):
        yield i // CHUNK, OS_ADDR + i, image[i:i + CHUNK]


def check(updater: Path, log: Path) -> int:
    """Every OS write in the log (12-byte header + sha256 of the rest) must match ours."""
    ours = {}
    for _, addr, data in os_writes(os_image(updater)):
        m = write(addr, data)
        ours[m[:12].hex(" ")] = hashlib.sha256(m[12:-1]).hexdigest()[:16]
    seen = bad = 0
    for line in log.read_text().splitlines():
        m = re.search(r"OUT .*len  2359  ((?:[0-9a-f]{2} ){12})\.\.\. \[2346 bytes, sha256 ([0-9a-f]{16})\]", line)
        if not m or m.group(1).strip() not in ours:
            continue
        seen += 1
        if ours[m.group(1).strip()] != m.group(2):
            bad += 1
            print("differs:", m.group(1))
    print(f"{seen} OS writes in the log, {bad} differ")
    return 0 if seen == OS_LEN // CHUNK and not bad else 1


class Pedal:
    def __init__(self):
        import mido
        from zoomms.midi import find_port
        self.mido = mido
        self.out = mido.open_output(find_port(mido.get_output_names()))
        self.inp = mido.open_input(find_port(mido.get_input_names()))

    def send(self, msg: bytes, timeout: float = 10.0) -> tuple[bytes | None, float]:
        """Send one SysEx, return (first reply or None on timeout, seconds)."""
        for _ in self.inp.iter_pending():
            pass
        t0 = time.monotonic()
        self.out.send(self.mido.Message("sysex", data=list(msg[1:-1])))
        while time.monotonic() - t0 < timeout:
            for r in self.inp.iter_pending():
                if r.type == "sysex":
                    return bytes([0xF0, *r.data, 0xF7]), time.monotonic() - t0
            time.sleep(0.001)
        return None, time.monotonic() - t0


def flash(updater: Path, bad: int | None) -> int:
    image = os_image(updater)
    pedal = Pedal()
    ident, _ = pedal.send(bytes([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]), 2)
    version = ident[10:14].decode("ascii", "replace") if ident else None
    print("identity:", version)
    if version != "1.10":
        print("not in update mode (the bootloader answers 1.10): hold the update switch while powering on")
        return 1

    def step(name: str, msg: bytes, timeout: float = 10.0) -> bool:
        reply, t = pedal.send(msg, timeout)
        if reply == ACK:
            return True
        print(f"{name}: {'no answer' if reply is None else reply.hex(' ')} after {t:.3f} s; stopping."
              " Flash with the release updater to recover.")
        return False

    if not (step("start", start()) and step("erase trailer", erase(TRAILER, 0x1000))
            and step("erase OS", erase(OS_ADDR, OS_LEN), 30)):
        return 1
    for n, addr, data in os_writes(image):
        if n == bad:
            reply, t = pedal.send(write(addr, data, bad_crc=True))
            print(f"bad CRC, chunk {n} (0x{addr:06X}): {'no answer' if reply is None else reply.hex(' ')} after {t:.3f} s")
            # A wrong answer may come with a second message, or the good resend may get none: both are results.
            time.sleep(0.5)
            extra = [bytes([0xF0, *r.data, 0xF7]).hex(" ") for r in pedal.inp.iter_pending() if r.type == "sysex"]
            if extra:
                print("then:", extra)
            reply, t = pedal.send(write(addr, data))
            print(f"good resend: {'no answer' if reply is None else reply.hex(' ')} after {t:.3f} s")
            if reply != ACK:
                print("stopping. Flash with the release updater to recover.")
                return 1
        elif not step(f"write chunk {n}", write(addr, data)):
            return 1
    if not step("finish", finish()):
        return 1
    print("done: restart the pedal; the identity should read M201")
    return 0


def _selftest() -> None:
    assert num(0x0EF000, 5) == bytes.fromhex("00603b0000")
    assert num(0x1000, 5) == bytes.fromhex("0020000000")
    assert erase(0x3FD000, 0x3000).hex() == "f05200610a00207f01000060000000f7"
    assert len(write(0, bytes(CHUNK))) == 2359
    assert pack7(bytes([0x80, 1, 0xFF])) == bytes([0b1010000, 0, 1, 0x7F])


if __name__ == "__main__":
    _selftest()
    cmd, exe = sys.argv[1], Path(sys.argv[2])
    if cmd == "check":
        sys.exit(check(exe, Path(sys.argv[3])))
    bad = int(sys.argv[sys.argv.index("--bad-crc") + 1]) if "--bad-crc" in sys.argv else None
    sys.exit(flash(exe, bad))
