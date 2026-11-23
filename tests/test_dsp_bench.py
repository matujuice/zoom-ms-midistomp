"""scripts/dsp_bench.py: packing, the 06 reply, the chain record (no pedal)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("dsp_bench", Path(__file__).parent.parent / "scripts" / "dsp_bench.py")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)


def test_pack_roundtrip():
    b = list(range(0, 256, 2)) + [0xFF, 0x80, 1]
    assert db.unpack7(db.pack7(b)) == b
    assert len(db.pack7([0] * 122)) == 140              # a 28 patch dump


def test_parse_bench():
    words = list(range(1000, 1000 + len(db.WORDS)))
    raw = b"".join(w.to_bytes(4, "little") for w in words)
    r = db.parse_bench(db.BENCH[:4] + [0x47, 0x11] + db.pack7(list(raw)))
    assert [r[k] for k in db.WORDS] == words
    assert db.parse_bench([0x52, 0, 0x61, 0x28]) is None


def test_build_chain():
    m = {"gid": 2, "fxid": 0x30, "params": [{"default": 100}, {"default": 3}]}
    rec = db.build_chain([0] * 122, [(m, 1)])
    key = ((2 << 24 | 0x30) << 1).to_bytes(4, "little")
    assert rec[0] == key[0] | 1 and rec[1] == key[1] & 7 and rec[3] & 0x1F == key[3] & 0x1F
    get = lambda x, w: sum((rec[(x + b) >> 3] >> ((x + b) & 7) & 1) << b for b in range(w))
    assert get(29, 13) == 100 and get(42, 13) == 3
    assert [rec[18 * s] for s in range(1, 6)] == [1] * 5    # empty slots
    t = rec[108] | rec[109] << 8 | rec[110] << 16
    assert t & 63 == 0 and t >> 10 & 7 == 1
