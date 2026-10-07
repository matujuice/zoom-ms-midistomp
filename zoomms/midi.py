"""MIDI SysEx transport. Only the read-only universal identity request for now."""

from __future__ import annotations

import time
from dataclasses import dataclass

ZOOM_MANUFACTURER = 0x52
IDENTITY_REQUEST = [0x7E, 0x00, 0x06, 0x01]  # mido adds F0/F7


@dataclass
class Identity:
    manufacturer: int
    family: int
    model: int
    version: str
    raw: list[int]


def parse_identity_reply(data: list[int]) -> Identity | None:
    """Parse the body (without F0/F7) of a universal identity reply:
    7E <ch> 06 02 <mfr> <family lo> <family hi> <model lo> <model hi> <v1..v4>.

    Zoom puts its model id (e.g. 0x5F) in the family field."""
    if len(data) < 13 or data[0] != 0x7E or data[2:4] != [0x06, 0x02]:
        return None
    version = "".join(chr(b) for b in data[9:13] if 0x20 <= b < 0x7F)
    return Identity(data[4], data[5] | data[6] << 7, data[7] | data[8] << 7, version, list(data))


def find_port(names: list[str]) -> str | None:
    for n in names:
        if "zoom" in n.lower() or "ms-" in n.lower():
            return n
    return None


def identify(port_name: str | None = None, timeout: float = 2.0) -> Identity | None:
    import mido

    port_name = port_name or find_port(mido.get_output_names())
    if port_name is None:
        raise RuntimeError("no Zoom MIDI port found; pass --port")
    in_name = find_port(mido.get_input_names()) if port_name not in mido.get_input_names() else port_name
    with mido.open_input(in_name) as inp, mido.open_output(port_name) as out:
        out.send(mido.Message("sysex", data=IDENTITY_REQUEST))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for msg in inp.iter_pending():
                if msg.type == "sysex":
                    ident = parse_identity_reply(list(msg.data))
                    if ident:
                        return ident
            time.sleep(0.01)
    return None
