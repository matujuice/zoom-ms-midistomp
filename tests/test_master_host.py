"""Host checks for asm/master/master.c (tests/master_host/): master_tap packing, the tuner, the loudness reading and
the six pages' framebuffers bit for bit against docs/dev/master-ui-mockup.html's own script (run with node).
The C is built at the mockup's 50 ms frame (-DMS_FRAME_MS=50); the pedal's 64 ms scales the falls."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOST = ROOT / "tests/master_host"


def _cc():
    try:
        spec = importlib.util.spec_from_file_location("perform_draw_preview", ROOT / "scripts/perform_draw_preview.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    except ImportError:
        return None
    return m.find_cc()


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    cc = _cc()
    if not cc or not (ROOT / "asm/master/master.c").exists():
        pytest.skip("no host C compiler (or master.c missing)")
    out = tmp_path_factory.mktemp("master") / "mh.exe"
    r = subprocess.run(cc + ["-O1", "-w", "-DMS_FRAME_MS=50", f"-I{HOST}", f"-I{ROOT / 'asm/master'}", f"-I{ROOT / 'asm/mixer'}",
                             str(HOST / "master_host.c"), "-o", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out


def test_tap_tuner_loudness(exe):
    r = subprocess.run([str(exe)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "tuner 440.0 Hz: note 69 cents 0" in r.stdout
    assert "inverse ok" in r.stdout


def test_pages_match_the_mockup(exe, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    subprocess.run([node, str(HOST / "master_ref.js"), str(ROOT / "docs/dev/master-ui-mockup.html"), str(tmp_path)], check=True)
    meta = json.loads((tmp_path / "meta.json").read_text())
    (tmp_path / "shots.txt").write_text("".join(f"{s['name']} {s['frame']}\n" for s in meta["shots"]))
    for s in meta["shots"]:
        (tmp_path / f"{s['name']}.fb").write_text(s["fb"])
    r = subprocess.run([str(exe), "ref", str(tmp_path / "audio.bin"), str(tmp_path / "shots.txt"), str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    diffs = {l.split()[1].rstrip(":"): int(l.split(":")[1].split()[0]) for l in r.stdout.splitlines() if l.startswith("shot ")}
    # scope: C steps the trigger search in float, the mockup in double; ~0.01 sample apart can flip a column or two
    assert len(diffs) == 9 and all(v <= (4 if n.startswith("scope") else 0) for n, v in diffs.items()), diffs
