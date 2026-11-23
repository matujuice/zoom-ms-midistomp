import importlib.util
from pathlib import Path

from zoomms import patcher

ROOT = Path(__file__).resolve().parent.parent
PATCH = patcher.load(ROOT / "patches/sysex-fx-slots.yaml")

spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_only_the_slot_limit_changes():
    (w,) = PATCH["write"]
    assert (w["model"], w["addr"]) == ("ms70cdr-2.10", 0xC00AEB94)
    old, new = (int.from_bytes(bytes.fromhex(w[k]), "little") for k in ("expect", "data"))
    assert old == 0x00104BDA                      # cmpltu .L2 2,b4,b0: slots 0-2 to fx_set_param
    field = 0x1F << 13                            # ucst5 src1
    assert old & ~field == new & ~field           # same opcode, registers and unit
    assert (old & field) >> 13 == 2 and (new & field) >> 13 == 5


def test_in_release_and_no_other_patch_writes_there():
    assert "sysex-fx-slots" in builder.PATCHES
    a = 0xC00AEB94
    for p in builder.PATCHES:
        patch = patcher.load(ROOT / "patches" / f"{p}.yaml")
        spans = [(s["addr"], len(bytes.fromhex("".join(s["data"].split())))) for s in patch.get("section", [])]
        spans += [(w["addr"], len(bytes.fromhex(w["data"]))) for w in patch.get("write", []) if p != "sysex-fx-slots"]
        assert not [s for s, n in spans if s < a + 4 and a < s + n], p
