"""Build the MASTER section of patches/mixer-m2.yaml with TI CGT 8.5
(asm/master/master_vec.asm + master.c, linked at 0xC010A000). Compares it with
the yaml, or --write replaces the yaml hex.

    py scripts/build_master_ui.py [--write]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_looper_ui import ROOT, available, main as _main, build as _build  # noqa: E402,F401

YAML = ROOT / "patches/mixer-m2.yaml"
ADDR, END = 0xC010A000, 0xC0110400            # code and small data; the buffers above (asm/master/master.h)
SOURCE = "asm/master/master.c"


def build() -> bytes:
    return _build((ROOT / "asm/master/master_vec.asm", ROOT / SOURCE), ADDR, END, "master_draw",
                  ("-ms3", "--disable_push_pop", "-I" + str(ROOT / "asm/mixer")))


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:], build(), YAML, SOURCE, ADDR))
