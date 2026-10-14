import struct

import pytest

from zoomms import macapp


def fake_app(tmp_path, script=macapp.SCRIPT):
    app = tmp_path / "Stock.app"
    res = macapp.resources(app)
    res.mkdir(parents=True)
    macapp.executable(app).parent.mkdir(parents=True)
    md5s = b""
    for i, name in enumerate(macapp.BIN_NAMES):
        data = bytes([i]) * 64
        (res / f"{name}.bin").write_bytes(data)
        md5s += macapp.md5_hex(data).encode() + b"\0"
    exe = b"\0" * 64 + b"".join(struct.pack("<4I", *s) for s in script) + b"\0" * 16 + md5s
    macapp.executable(app).write_bytes(exe)
    return app


def test_find_script(tmp_path):
    exe = macapp.executable(fake_app(tmp_path)).read_bytes()
    steps = macapp.find_script(exe)
    assert [(s.kind, s.addr, s.length, s.file) for s in steps] == macapp.SCRIPT
    assert steps[0].offset == 64


def test_find_script_rejects_unknown_layout(tmp_path):
    script = list(macapp.SCRIPT)
    script[2] = (macapp.WRITE, 0, 0x40000, 1)
    with pytest.raises(ValueError):
        macapp.find_script(macapp.executable(fake_app(tmp_path, script)).read_bytes())


def test_build_app(tmp_path):
    app = fake_app(tmp_path)
    out = tmp_path / "Mod.app"
    new_os, new_133 = b"\x77" * 64, b"\x88" * 64
    steps = macapp.build_app(app, out, new_os, new_133=new_133)
    assert [s.kind for s in steps] == [macapp.ERASE, macapp.SKIP, macapp.SKIP,
                                       macapp.ERASE, macapp.WRITE, macapp.ERASE, macapp.WRITE]
    res = macapp.resources(out)
    assert (res / "Main.bin").read_bytes() == new_os
    assert (res / "Preset.bin").read_bytes() == new_133
    assert (res / "boot.bin").read_bytes() == (macapp.resources(app) / "boot.bin").read_bytes()
    exe = macapp.executable(out).read_bytes()
    assert macapp.md5_hex(new_os).encode() in exe and macapp.md5_hex(new_133).encode() in exe
    assert macapp.md5_hex(bytes([0]) * 64).encode() not in exe
    stock = macapp.executable(app).read_bytes()
    assert len(exe) == len(stock)


def test_build_app_skips_preset_without_new_133(tmp_path):
    steps = macapp.build_app(fake_app(tmp_path), tmp_path / "Mod.app", b"\x77" * 64)
    assert [s.kind for s in steps][1:5] == [macapp.SKIP] * 4


def test_build_app_refuses_modified_resources(tmp_path):
    app = fake_app(tmp_path)
    (macapp.resources(app) / "boot.bin").write_bytes(b"\x99" * 64)
    with pytest.raises(ValueError):
        macapp.build_app(app, tmp_path / "Mod.app", b"\x77" * 64)
    assert not (tmp_path / "Mod.app").exists()


def test_build_app_refuses_size_change(tmp_path):
    with pytest.raises(ValueError):
        macapp.build_app(fake_app(tmp_path), tmp_path / "Mod.app", b"\x77" * 65)
