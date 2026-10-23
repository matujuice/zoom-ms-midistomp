import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("chain_draw_preview", ROOT / "scripts/chain_draw_preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

NAMES = ["a_parallel", "b_serial", "c_empty_route", "d_scroll", "e_selected_bus", "f_delete_limit"]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("chain-preview")
    if preview.run(d) is None:
        pytest.skip("no host C compiler")
    return d


def px(fb, x, y):
    return fb[y * 16 + x // 8] >> (7 - x % 8) & 1


def test_six_states_rendered(out):
    for n in NAMES:
        assert len((out / f"{n}.fb").read_bytes()) == 1024
        assert (out / f"{n}.png").stat().st_size > 0


def test_bars_and_cursor(out):
    fb = (out / "a_parallel.fb").read_bytes()
    assert all(px(fb, x, 0) for x in range(128))        # title bar
    assert all(px(fb, x, 63) for x in range(2, 42))     # first softkey, stock box x 2-41
    assert px(fb, 43, 10) and not px(fb, 44, 11)        # cursor outline, then the 1-px gap, around the A cover at (45, 12)
    assert fb != (out / "b_serial.fb").read_bytes()


def test_limit_tag(out):
    # state f: the cursor is on the Post effect, so OUT is the left column (x 3) and the tag box starts at (12, 29)
    fb = (out / "f_delete_limit.fb").read_bytes()
    assert px(fb, 12, 29) and px(fb, 32, 35)
