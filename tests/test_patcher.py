import pytest

from zoomms import ais, patcher
from tests.test_ais import make_ais


def img_with(text: bytes):
    img = ais.parse(make_ais())
    img.sections[0].data = text
    return img


def test_replace_same_length_everywhere():
    img = img_with(b"VERSION\0xxVERSION\0")
    log = patcher.apply(img, {"name": "t", "replace": [{"find": "VERSION\0", "with": "MOD 0.1\0", "count": 2}]}, "any")
    assert img.sections[0].data == b"MOD 0.1\0xxMOD 0.1\0" and len(log) == 2


def test_replace_count_mismatch_fails():
    with pytest.raises(patcher.PatchError):
        patcher.apply(img_with(b"VERSION\0"), {"name": "t", "replace": [{"find": "VERSION\0", "with": "MOD 0.1\0", "count": 2}]}, "any")


def test_write_checks_expected_bytes():
    img = img_with(b"abcdef")
    p = {"name": "t", "write": [{"model": "m", "addr": 0x11800002, "expect": "6364", "data": "5858"}]}
    patcher.apply(img, p, "m")
    assert img.sections[0].data == b"abXXef"
    with pytest.raises(patcher.PatchError):
        patcher.apply(img, p, "m")


def test_build_round_trip_and_new_section():
    raw = make_ais()
    img = ais.parse(raw)
    assert ais.build(img) == raw[:img.end_offset]
    img.add_section(0x11900000, b"\x01\x02\x03\x04")
    again = ais.parse(ais.build(img))
    assert [s.addr for s in again.sections] == [0x11800000, 0x11900000]
    assert again.entry == img.entry


def test_bin133_checks_stock_hash():
    import hashlib
    part = bytearray(b"\0" * 16)
    p = {"name": "t", "bin133": [{"model": "m", "offset": 4, "expect_sha256": hashlib.sha256(b"\0\0").hexdigest(), "data": "abcd"}]}
    assert patcher.apply(img_with(b"x"), p, "m") == []  # OS untouched, not an error
    patcher.apply_bin133(part, p, "m")
    assert part[4:6] == b"\xab\xcd"
    with pytest.raises(patcher.PatchError):
        patcher.apply_bin133(part, p, "m")


def test_boot_logo_patch_is_one_screen():
    p = patcher.load("patches/boot-logo.yaml")
    assert [(b["offset"], len(bytes.fromhex(b["data"]))) for b in p["bin133"]] == [(0, 1024)]
