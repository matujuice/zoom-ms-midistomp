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
