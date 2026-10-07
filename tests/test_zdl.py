import os
import struct
from pathlib import Path

import pytest

from zoomms import zdl


def make_zdl(real_type=8, elf=b"\x7fELF" + b"\x01\x01\x01" + b"\0" * 11 + struct.pack("<H", 140) + b"\0" * 32):
    info = b"ZOOM EFFECT DLL SYSTEM VER 1.00\0" + bytes([real_type, 1, 0, 0, 250, 0, 0, real_type]) + b"1.01\0\0\0\0"
    return b"\0" * 4 + b"SIZE" + struct.pack("<III", 8, 56, len(elf)) + b"INFO" + struct.pack("<I", 48) + info + elf


def test_parse_synthetic():
    z = zdl.parse(make_zdl())
    assert z.category == "Delay"
    assert z.fx_version == "1.01"
    assert z.elf_machine == zdl.EM_TI_C6000


def test_rejects_non_zdl():
    with pytest.raises(zdl.ZdlError):
        zdl.parse(b"MZ" + b"\0" * 100)


CORPUS = os.environ.get("ZOOMMS_ZDL_CORPUS")


@pytest.mark.skipif(not CORPUS, reason="set ZOOMMS_ZDL_CORPUS to a folder of stock .ZDL files")
def test_stock_corpus_parses():
    paths = sorted(Path(CORPUS).rglob("*.ZDL"))
    assert paths
    bad = []
    for p in paths:
        try:
            assert zdl.load(p).elf_machine == zdl.EM_TI_C6000
        except (zdl.ZdlError, AssertionError) as e:
            bad.append(f"{p.name}: {e}")
    assert not bad, bad[:10]
