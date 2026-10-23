"""Build the DIAGNOSTICS section of patches/diag.yaml with TI CGT 8.5
(asm/diag/diag_vec.asm + diag.c, linked at 0xC00F3100). Compares it with the
yaml, or --write replaces the yaml hex.

    py scripts/build_diag_ui.py [--write]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_looper_ui import ROOT, available, main as _main, build as _build  # noqa: E402,F401

YAML = ROOT / "patches/diag.yaml"
ADDR, END = 0xC00F3100, 0xC00F5400            # after the looper services, before lbox.c
SOURCE = "asm/diag/diag.c"


def build() -> bytes:
    return _build((ROOT / "asm/diag/diag_vec.asm", ROOT / SOURCE), ADDR, END, "diag_end", ("-ms0", "--disable_push_pop"))


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:], build(), YAML, SOURCE, ADDR))
