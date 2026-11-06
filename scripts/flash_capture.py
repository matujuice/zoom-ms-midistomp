"""Record a Zoom updater flash over USB and write a log without the firmware bytes.

Windows, USBPcap installed (winget install desowin.USBPcap, then reboot).

  py scripts/flash_capture.py record OUTDIR   # asks for admin, records every USB root hub
                                              # until OUTDIR/stop exists (or Enter)
  py scripts/flash_capture.py log OUTDIR      # OUTDIR/*.pcap -> OUTDIR/flash-log.txt

The log keeps every SysEx to and from the Zoom device (vendor 0x1686) with its time and
length; a long message keeps only its first HEAD bytes plus a sha256 of the rest, so no
Zoom firmware data ends up in it. The .pcap files hold everything: never share them.
"""

from __future__ import annotations

import ctypes
import hashlib
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

USBPCAP = r"C:\Program Files\USBPcap\USBPcapCMD.exe"
ZOOM_VID = 0x1686
HEAD = 16  # bytes of a long SysEx kept in the log (command and address, never the data)
SHORT = 32  # SysEx up to this length is logged whole


def hubs() -> list[str]:
    out = subprocess.run([USBPCAP, "--extcap-interfaces"], capture_output=True, text=True).stdout
    return re.findall(r"\{value=(\\\\\.\\USBPcap\d+)\}", out)


def record(outdir: Path) -> int:
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Re-run elevated in its own window; UAC asks once.
        args = f'"{Path(__file__).resolve()}" record "{outdir.resolve()}"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
        print(f"started elevated; create {outdir / 'stop'} (or press Enter there) to stop")
        return 0
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "stop").unlink(missing_ok=True)
    names = hubs()
    if not names:
        print("no USBPcap hubs: reboot after installing USBPcap")
        input()
        return 1
    procs = [subprocess.Popen([USBPCAP, "-d", h, "-A", "--inject-descriptors",
                               "-o", str(outdir / f"hub{h[-1]}.pcap")]) for h in names]
    (outdir / "recording").write_text(" ".join(names))
    print("recording", names, "- press Enter or create", outdir / "stop")
    import msvcrt
    while not (outdir / "stop").exists() and not msvcrt.kbhit():
        time.sleep(0.2)
    for p in procs:
        p.terminate()
    (outdir / "recording").unlink(missing_ok=True)
    return 0


def packets(path: Path):
    """Yield (time, device, endpoint, transfer, data) from a USBPcap pcap file."""
    raw = path.read_bytes()
    if len(raw) < 24:
        return
    magic = struct.unpack_from("<I", raw)[0]
    assert magic == 0xA1B2C3D4, f"{path}: not a little-endian pcap"
    assert struct.unpack_from("<I", raw, 20)[0] == 249, f"{path}: not USBPcap (linktype 249)"
    off = 24
    while off + 16 <= len(raw):
        sec, usec, incl, _ = struct.unpack_from("<IIII", raw, off)
        rec = raw[off + 16:off + 16 + incl]
        off += 16 + incl
        if len(rec) < 27:
            continue
        hlen, _irp, _st, _fn, info, _bus, dev, ep, xfer, dlen = struct.unpack_from("<HQIHBHHBBI", rec)
        yield sec + usec / 1e6, dev, ep, xfer, info, rec[hlen:hlen + dlen]


def zoom_devices(files: list[Path]) -> set[int]:
    """Device addresses whose device descriptor (12 01 ...) names vendor 0x1686."""
    found = set()
    for f in files:
        for _t, dev, _ep, xfer, _info, data in packets(f):
            if xfer == 2 and len(data) >= 10 and data[0] == 0x12 and data[1] == 0x01:
                if struct.unpack_from("<H", data, 8)[0] == ZOOM_VID:
                    found.add((f.name, dev))
    return found


def sysex_stream(data: bytes, buf: bytearray):
    """USB-MIDI 4-byte events -> completed SysEx messages (CIN 4 = start/continue, 5-7 = end)."""
    for i in range(0, len(data) - 3, 4):
        cin = data[i] & 0x0F
        if cin == 0x4:
            buf += data[i + 1:i + 4]
        elif cin in (0x5, 0x6, 0x7):
            buf += data[i + 1:i + 1 + (cin - 4)]
            yield bytes(buf)
            buf.clear()


def short(msg: bytes) -> str:
    if len(msg) <= SHORT:
        return msg.hex(" ")
    rest = msg[HEAD:-1]
    return f"{msg[:HEAD].hex(' ')} ... [{len(rest)} bytes, sha256 {hashlib.sha256(rest).hexdigest()[:16]}] {msg[-1:].hex()}"


def log(outdir: Path) -> int:
    files = sorted(outdir.glob("*.pcap"))
    zoom = zoom_devices(files)
    if not zoom:
        print("no Zoom device descriptor in the capture; logging every bulk device")
    lines, t0 = [], None
    bufs: dict = {}
    for f in files:
        for t, dev, ep, xfer, info, data in packets(f):
            if xfer != 3 or not data or (zoom and (f.name, dev) not in zoom):
                continue
            # OUT data rides on the request (info bit 0 clear), IN data on the completion.
            if bool(ep & 0x80) != bool(info & 1):
                continue
            t0 = t if t0 is None else t0
            key = (f.name, dev, ep)
            for msg in sysex_stream(data, bufs.setdefault(key, bytearray())):
                lines.append((t, f"{t - t0:9.3f}  {'IN ' if ep & 0x80 else 'OUT'} ep{ep & 0x7F:02X} "
                                 f"len {len(msg):5d}  {short(msg)}"))
    lines.sort()
    text = "\n".join(l for _, l in lines) + "\n"
    (outdir / "flash-log.txt").write_text(text)
    print(f"{len(lines)} SysEx messages -> {outdir / 'flash-log.txt'}")
    return 0


def _selftest() -> None:
    # F0 01 02 03 04 F7 as USB-MIDI events: CIN 4 (start, 3 bytes), CIN 7 (end, 3 bytes).
    ev = bytes([0x04, 0xF0, 0x01, 0x02, 0x07, 0x03, 0x04, 0xF7])
    assert list(sysex_stream(ev, bytearray())) == [bytes([0xF0, 1, 2, 3, 4, 0xF7])]
    long = bytes([0xF0]) + bytes(range(1, 41)) + bytes([0xF7])
    s = short(long)
    assert s.startswith(long[:HEAD].hex(" ") + " ...") and "[25 bytes" in s


if __name__ == "__main__":
    _selftest()
    cmd, outdir = sys.argv[1], Path(sys.argv[2])
    sys.exit(record(outdir) if cmd == "record" else log(outdir))
