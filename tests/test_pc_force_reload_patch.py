import importlib.util
from pathlib import Path

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/pc-force-reload.yaml")

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_one_compact_halfword():
    (w,) = PATCH["write"]
    assert (w["model"], w["addr"]) == ("ms70cdr-2.10", 0xC00ADF90)
    assert w["expect"] == "c780"   # || mv .L2 b1,b4: old = the current patch
    # || mvk .L2 -1,b4: old = -1. Same halfword the stock OS uses for that argument at 0xC00AEC08 / 0xC00AEC36.
    assert w["data"] == "27fe"


def test_in_release_and_no_other_patch_writes_there():
    assert "pc-force-reload" in builder.PATCHES
    a = 0xC00ADF90
    for p in builder.PATCHES:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        spans = [(s["addr"], len(bytes.fromhex("".join(s["data"].split())))) for s in patch.get("section", [])]
        spans += [(w["addr"], len(bytes.fromhex(w["data"]))) for w in patch.get("write", []) if p != "pc-force-reload"]
        assert not [s for s, n in spans if s < a + 2 and a < s + n], p
