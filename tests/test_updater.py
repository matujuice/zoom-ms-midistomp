import struct

from zoomms import updater as u


def make_updater(files: dict[str, bytes], data_blocks: int = 64, prefix: bytes = b"MZ" + b"\0" * 100) -> bytes:
    """Build a synthetic updater image following the documented layout."""
    total = u.FIRST_DATA_BLOCK + data_blocks
    img = bytearray(b"\xff") * (total * u.BLOCK)
    img[:6] = u.BIN_START
    struct.pack_into("<H", img, 8, total)
    table = bytearray(b"\xff") * u.TABLE_SIZE
    table[1], table[5] = 0xA5, 0xFF
    next_free = 1
    for i, (name, content) in enumerate(files.items()):
        chunks = [content[j:j + u.PAYLOAD] for j in range(0, len(content), u.PAYLOAD)] or [b""]
        blocks = list(range(next_free, next_free + len(chunks)))
        next_free += len(chunks)
        entry = bytearray(b"\xff") * u.ENTRY
        struct.pack_into("<HHI", entry, 0, blocks[0], 0x01FF, len(content))
        entry[8:20] = name.encode().ljust(12, b"\0")
        table[u.TABLE_HEADER + i * u.ENTRY:u.TABLE_HEADER + (i + 1) * u.ENTRY] = entry
        for k, (b, c) in enumerate(zip(blocks, chunks)):
            off = (u.FIRST_DATA_BLOCK + b) * u.BLOCK
            prev = blocks[k - 1] if k else u.END
            nxt = blocks[k + 1] if k + 1 < len(blocks) else u.END
            struct.pack_into("<HHH", img, off, prev, nxt, len(c))
            img[off + 6:off + 6 + len(c)] = c
    pos = 3 * u.BLOCK
    img[pos:pos + u.TABLE_SIZE] = table
    return prefix + bytes(img) + b"trailer"


FILES = {"A.ZDL": bytes(range(256)) * 40, "B.ZDL": b"x" * 10, "FLST_SEQ.ZT2": b"\x01\x02"}


def test_parse_lists_files_and_contents():
    fw = u.parse(make_updater(FILES))
    assert fw.problems == []
    assert {f.name: f.content for f in fw.files} == FILES
    assert fw.file("A.ZDL").blocks == [1, 2, 3]


def test_round_trip_is_exact():
    fw = u.parse(make_updater(FILES))
    assert u.rebuild(fw) == fw.image


def test_broken_chain_is_reported():
    data = bytearray(make_updater(FILES))
    fw = u.parse(bytes(data))
    off = fw.offset + (u.FIRST_DATA_BLOCK + 2) * u.BLOCK
    struct.pack_into("<H", data, off, 99)  # corrupt prev pointer of A.ZDL's 2nd block
    assert any("prev=99" in p for p in u.parse(bytes(data)).problems)
