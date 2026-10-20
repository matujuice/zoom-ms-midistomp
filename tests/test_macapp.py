import struct
from pathlib import Path

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
    if script == macapp.SCRIPT_70CDR:  # the 70CDR app's model check, its list 0x39 bytes after the leaq
        loop = bytearray(b"\x90" * 16 + MODEL_LOOP_CODE + bytes(64))
        struct.pack_into("<2I", loop, 16 + 18 + 0x39, 0x57, 0x61)
        exe += bytes(loop)
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


def test_build_app_70cdr_skips_effects_steps(tmp_path):
    steps = macapp.build_app(fake_app(tmp_path, macapp.SCRIPT_70CDR), tmp_path / "Mod.app", b"\x77" * 64)
    assert [s.kind for s in steps] == [macapp.ERASE] + [macapp.SKIP] * 6 + [macapp.ERASE, macapp.WRITE]


# The model check loop as in the MS-70CDR v2.10 app, its list 0x40 bytes after the leaq.
MODEL_LOOP_CODE = bytes.fromhex("48837de802" "0f835b000000" "488d0539000000" "488b4de8" "48c1e102" "4801c8" "8b10"
                                "8b35" "00000000")


def test_accept_models():
    exe = bytearray(b"\x90" * 16 + MODEL_LOOP_CODE + bytes(64))
    table = 16 + 18 + 0x39
    struct.pack_into("<2I", exe, table, 0x57, 0x61)
    assert macapp.accept_models(exe)
    assert exe[table:table + 8] == bytes([0x57, 0x58, 0x5F, 0x61, 0, 0, 0, 0])
    assert exe[16 + 4] == 4
    assert exe[16 + 22:16 + 31] == bytes.fromhex("0fb614080f1f440000")
    assert not macapp.accept_models(exe)  # already patched


def test_accept_models_absent():
    assert not macapp.accept_models(bytearray(bytes(64)))


def test_build_app_70cdr_with_new_preset(tmp_path):
    # The real v1.2 build: boot logo in Preset.bin, so only boot and FS steps are skipped.
    steps = macapp.build_app(fake_app(tmp_path, macapp.SCRIPT_70CDR), tmp_path / "Mod.app", b"\x77" * 64,
                             new_133=b"\x88" * 64)
    assert [s.kind for s in steps] == [macapp.ERASE, macapp.SKIP, macapp.SKIP, macapp.ERASE, macapp.WRITE,
                                       macapp.SKIP, macapp.SKIP, macapp.ERASE, macapp.WRITE]


def test_find_script_rejects_unknown_70cdr_layout(tmp_path):
    script = list(macapp.SCRIPT_70CDR)
    script[6] = (macapp.WRITE, 0x0F0000, 0x2C7000, 2)  # FS write pointing at Preset.bin
    with pytest.raises(ValueError):
        macapp.find_script(macapp.executable(fake_app(tmp_path, script)).read_bytes())


def test_accept_models_other_list():
    exe = bytearray(b"\x90" * 16 + MODEL_LOOP_CODE + bytes(64))
    struct.pack_into("<2I", exe, 16 + 18 + 0x39, 0x57, 0x58)  # the MS-50G list
    before = bytes(exe)
    assert not macapp.accept_models(exe)
    assert exe == before


def test_build_app_real_70cdr(tmp_path):
    # Needs Zoom's MS-70CDR 2.10 Mac updater (never committed): MIDISTOMP_70CDR_MAC_APP=path/to/.app
    import os
    app = os.environ.get("MIDISTOMP_70CDR_MAC_APP")
    if not app:
        pytest.skip("no MS-70CDR Mac updater")
    res = macapp.resources(Path(app))
    new_os = bytearray((res / "Main.bin").read_bytes())
    new_os[0x1000] ^= 0xFF
    new_133 = bytearray((res / "Preset.bin").read_bytes())
    new_133[0] ^= 0xFF
    out = tmp_path / "Mod.app"
    steps = macapp.build_app(app, out, bytes(new_os), new_133=bytes(new_133), title="MIDISTOMP V1.2 Updater")
    assert [s.kind for s in steps] == [macapp.ERASE, macapp.SKIP, macapp.SKIP, macapp.ERASE, macapp.WRITE,
                                       macapp.SKIP, macapp.SKIP, macapp.ERASE, macapp.WRITE]
    stock = macapp.executable(Path(app)).read_bytes()
    exe = macapp.executable(out).read_bytes()
    assert len(exe) == len(stock)
    title = stock.find(b"ZOOM MS-70CDR v2.10 Updater\0")
    assert exe[title:title + 28] == b"MIDISTOMP V1.2 Updater" + bytes(6)
    cfstr = stock.find(struct.pack("<QQ", macapp.TEXT_VMADDR + title, 27))
    assert struct.unpack_from("<Q", exe, cfstr + 8)[0] == 22
    md5s = set(range(title, title + 27)) | set(range(cfstr + 8, cfstr + 9))
    for name in ("Main", "Preset"):
        at = stock.find(macapp.md5_hex((res / f"{name}.bin").read_bytes()).encode())
        md5s |= set(range(at, at + 32))
    changed = {i for i in range(len(stock)) if stock[i] != exe[i]} - md5s
    # model loop: bound 2 -> 4 at 0x5680, movzbl + nop at 0x5692; step types; the list
    assert changed == ({0x5680} | set(range(0x5692, 0x569B)) | {0x21760, 0x21770, 0x217A0, 0x217B0}
                       | set(range(0x217E1, 0x217E5)))
    assert exe[0x217E0:0x217E8] == bytes([0x57, 0x58, 0x5F, 0x61, 0, 0, 0, 0])
    assert exe[0x5692:0x569B] == bytes.fromhex("0fb614080f1f440000")
    assert macapp.md5_hex(bytes(new_os)).encode() in exe and macapp.md5_hex(bytes(new_133)).encode() in exe


def cfstring_exe(title=b"ZOOM MS-70CDR v2.10 Updater"):
    exe = bytearray(64) + b"\0" + title + b"\0bin\0" + bytes(16)
    exe += struct.pack("<QQQQ", 0, 0x7C8, macapp.TEXT_VMADDR + 65, len(title))
    return exe


def test_set_title():
    exe = cfstring_exe()
    macapp.set_title(exe, "ZOOM MS-70CDR v2.10 Updater", "MIDISTOMP V1.2 Updater")
    assert exe[65:65 + 28] == b"MIDISTOMP V1.2 Updater" + bytes(6)
    assert exe[65 + 28:65 + 32] == b"bin\0"
    assert struct.unpack_from("<Q", exe, len(exe) - 8)[0] == 22


def test_set_title_too_long():
    with pytest.raises(ValueError):
        macapp.set_title(cfstring_exe(), "ZOOM MS-70CDR v2.10 Updater", "Zoom MS MIDISTOMP Custom Updater")


def test_build_app_70cdr_needs_model_check(tmp_path):
    app = fake_app(tmp_path, macapp.SCRIPT_70CDR)
    exe = macapp.executable(app)
    exe.write_bytes(exe.read_bytes().replace(MODEL_LOOP_CODE[:7], b"\x90" * 7))
    with pytest.raises(ValueError):
        macapp.build_app(app, tmp_path / "Mod.app", b"\x77" * 64)
    assert not (tmp_path / "Mod.app").exists()


def test_find_title():
    assert macapp.find_title(bytes(cfstring_exe())) == "ZOOM MS-70CDR v2.10 Updater"
    with pytest.raises(ValueError):
        macapp.find_title(bytes(64))


def test_set_title_ascii_only():
    with pytest.raises(ValueError):
        macapp.set_title(cfstring_exe(), "ZOOM MS-70CDR v2.10 Updater", "MIDISTOMP V1.2 Updatér")
