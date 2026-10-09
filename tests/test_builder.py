import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("builder", Path(__file__).parent.parent / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_refuses_other_files(tmp_path):
    f = tmp_path / "x.exe"
    f.write_bytes(b"not zoom")
    assert builder.run([str(f)]) == 1
    assert not (tmp_path / builder.OUT_NAME).exists()


def test_patch_files_exist():
    assert all((builder.ROOT / "patches" / f"{p}.yaml").exists() for p in builder.PATCHES)
