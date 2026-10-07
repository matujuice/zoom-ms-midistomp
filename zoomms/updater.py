"""Read-only parser for the flash image embedded in Zoom's official updaters.

Format as documented by Zoom-Firmware-Editor (MIT, Barsik-Barbosik):

* The image starts at the pattern ``55 AA 00 01 04 00`` somewhere inside the
  updater executable. A little-endian u16 at +8 is the image size in 4 KiB blocks.
* Blocks 0-2 are system blocks. Four copies of the file table live at blocks
  3, 5, 7 and 9, each two blocks long. A copy is valid when byte +1 is 0xA5 and
  byte +5 is 0xFF; the live copy also has 0xFF at +4.
* Each table entry is 32 bytes (after an 8-byte table header): u16 first data
  block at +0, u32 size at +4, NUL-terminated 12-byte name at +8. An entry
  whose first 8 bytes are all 0xFF is empty.
* Data block N sits at image block 10 + N. Each block has a 6-byte header
  (u16 prev, u16 next, u16 payload length) followed by up to 4090 bytes of
  payload. 0xFFFF marks the end of a chain.

Nothing in this module writes to a pedal.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

BIN_START = bytes.fromhex("55AA00010400")
BLOCK = 4096
SYS_BLOCKS = 11
FIRST_DATA_BLOCK = 10
TABLE_BLOCKS = (3, 5, 7, 9)
TABLE_HEADER = 8
TABLE_SIZE = 2 * BLOCK
ENTRY = 32
BLOCK_HEADER = 6
PAYLOAD = BLOCK - BLOCK_HEADER
END = 0xFFFF


class UpdaterError(ValueError):
    pass


@dataclass
class FileEntry:
    name: str
    first_block: int
    size: int
    raw_entry: bytes
    blocks: list[int] = field(default_factory=list)
    content: bytes = b""


@dataclass
class FlashImage:
    updater: bytes
    offset: int
    block_count: int
    table_block: int
    files: list[FileEntry]
    problems: list[str]

    @property
    def image(self) -> bytes:
        return self.updater[self.offset:self.offset + self.block_count * BLOCK]

    def file(self, name: str) -> FileEntry:
        for f in self.files:
            if f.name == name:
                return f
        raise KeyError(name)


def _table_valid(img: bytes, pos: int) -> bool:
    return img[pos + 1] == 0xA5 and img[pos + 5] == 0xFF


def _data_off(block: int) -> int:
    return (FIRST_DATA_BLOCK + block) * BLOCK


def parse(updater: bytes) -> FlashImage:
    offset = updater.find(BIN_START)
    if offset < 0:
        raise UpdaterError("flash image start pattern not found")
    (block_count,) = struct.unpack_from("<H", updater, offset + 8)
    img = updater[offset:offset + block_count * BLOCK]
    if len(img) != block_count * BLOCK:
        raise UpdaterError(f"image truncated: header says {block_count} blocks")

    valid = [b for b in TABLE_BLOCKS if _table_valid(img, b * BLOCK)]
    if not valid:
        raise UpdaterError("no valid file table found")
    live = [b for b in valid if img[b * BLOCK + 4] == 0xFF]
    table_block = live[0] if live else valid[-1]

    problems: list[str] = []
    files: list[FileEntry] = []
    owner: dict[int, str] = {0: "<reserved>"}
    base = table_block * BLOCK
    for pos in range(base + TABLE_HEADER, base + TABLE_SIZE, ENTRY):
        raw = img[pos:pos + ENTRY]
        if raw[:8] == b"\xff" * 8:
            continue
        name = raw[8:20].split(b"\x00", 1)[0].decode("latin-1")
        if not name:
            continue
        first, = struct.unpack_from("<H", raw, 0)
        size, = struct.unpack_from("<I", raw, 4)
        entry = FileEntry(name, first, size, raw)
        _read_chain(img, entry, owner, problems)
        files.append(entry)
    return FlashImage(updater, offset, block_count, table_block, files, problems)


def _read_chain(img: bytes, entry: FileEntry, owner: dict[int, str], problems: list[str]) -> None:
    data_blocks = len(img) // BLOCK - FIRST_DATA_BLOCK
    chunks = []
    prev, block = END, entry.first_block
    while block != END:
        if not 0 < block < data_blocks:
            problems.append(f"{entry.name}: block {block} out of range")
            return
        if block in owner:
            problems.append(f"{entry.name}: block {block} already used by {owner[block]}")
            return
        owner[block] = entry.name
        off = _data_off(block)
        p, n, length = struct.unpack_from("<HHH", img, off)
        if prev != END and p != prev:
            problems.append(f"{entry.name}: block {block} prev={p}, expected {prev}")
        if length > PAYLOAD:
            problems.append(f"{entry.name}: block {block} payload length {length} too large")
            return
        chunks.append(img[off + BLOCK_HEADER:off + BLOCK_HEADER + length])
        entry.blocks.append(block)
        prev, block = block, n
    entry.content = b"".join(chunks)
    if len(entry.content) != entry.size:
        problems.append(f"{entry.name}: read {len(entry.content)} bytes, table says {entry.size}")


def rebuild(fw: FlashImage, fill: int = 0xFF) -> bytes:
    """Re-serialise the image from the parsed file list, keeping each file's
    original block chain.

    Only the live file table and the blocks owned by live files are generated.
    The system blocks, the older file-table copies (each table header starts
    with a generation counter; the live one is the newest) and free data blocks
    (which in stock updaters still hold stale chains from earlier builds) are
    copied from the source. Slack after a block's payload comes out as ``fill``.

    So an exact match with ``fw.image`` means every byte of the live file
    system is understood. A modified image must never be flashed until this
    round trip is exact for the stock updater it came from.
    """
    src = fw.image
    out = bytearray(src)
    pos = fw.table_block * BLOCK
    out[pos + TABLE_HEADER:pos + TABLE_SIZE] = b"\xff" * (TABLE_SIZE - TABLE_HEADER)
    for i, f in enumerate(fw.files):
        p = pos + TABLE_HEADER + i * ENTRY
        out[p:p + ENTRY] = f.raw_entry
    for f in fw.files:
        for block in f.blocks:
            off = _data_off(block)
            out[off:off + BLOCK] = bytes([fill]) * BLOCK
    for f in fw.files:
        for i, block in enumerate(f.blocks):
            prev = f.blocks[i - 1] if i else END
            nxt = f.blocks[i + 1] if i + 1 < len(f.blocks) else END
            chunk = f.content[i * PAYLOAD:(i + 1) * PAYLOAD]
            off = _data_off(block)
            out[off:off + BLOCK_HEADER] = struct.pack("<HHH", prev, nxt, len(chunk))
            out[off + BLOCK_HEADER:off + BLOCK_HEADER + len(chunk)] = chunk
    return bytes(out)


def diff_blocks(a: bytes, b: bytes) -> list[int]:
    """Return the indices of image blocks that differ."""
    return [i // BLOCK for i in range(0, len(a), BLOCK) if a[i:i + BLOCK] != b[i:i + BLOCK]]


def free_blocks(fw: FlashImage) -> tuple[int, int]:
    """Return (free data blocks, of which still holding stale data)."""
    used = {b for f in fw.files for b in f.blocks} | {0}
    img = fw.image
    free = [b for b in range(fw.block_count - FIRST_DATA_BLOCK) if b not in used]
    stale = sum(1 for b in free if img[_data_off(b):_data_off(b) + BLOCK] != b"\xff" * BLOCK)
    return len(free), stale


def load(path: str | Path) -> FlashImage:
    return parse(Path(path).read_bytes())
