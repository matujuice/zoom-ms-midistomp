"""MIDISTOMP-builder: drop Zoom's official MS-50G 3.10 updater on this program
and it writes the MIDISTOMP V1.0 updater next to it.

Same output as `zoomms build` with the v1.0 patch set (docs/flashing.md).
Refuses any file that is not the stock updater (sha256 in models/ms50g.yaml).
Frozen into MIDISTOMP-builder.exe by .github/workflows/builder.yml.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from zoomms import cli, models

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
NAME = "MIDISTOMP V1.0"
PATCHES = ["version-1.0", "boot-logo", "midi-cc", "midi-clock", "midi-settings", "tempo-hold"]
OUT_NAME = "MIDISTOMP V1.0 Updater.exe"


def build(updater: Path, out: Path) -> int:
    argv = ["build", str(updater), "--build-id", "ms50g-3.10", "--out", str(out)]
    for p in PATCHES:
        argv += ["--patch", str(ROOT / "patches" / f"{p}.yaml")]
    return cli.main(argv)


def run(args: list[str]) -> int:
    if len(args) != 1:
        print(f"{NAME} builder\n\nDrag Zoom's official MS-50G v3.10 updater "
              "(ZOOM MS-50G System v3.10 Updater.exe) onto this program.")
        return 1
    updater = Path(args[0])
    want = models.load_all(ROOT / "models")["ms50g"]["stock_updater_sha256"]
    try:
        got = hashlib.sha256(updater.read_bytes()).hexdigest()
    except OSError as e:
        print(f"Cannot read {updater}: {e}")
        return 1
    if got != want:
        print(f"{updater.name} is not Zoom's official MS-50G v3.10 updater.\n"
              f"sha256 {got}\nexpected {want}\nNothing was written.")
        return 1
    out = updater.with_name(OUT_NAME)
    if build(updater, out):
        print("Build failed, nothing usable was written.")
        return 1
    print(f"\nDone: {out}\nFlash it in update mode (see the MIDISTOMP user guide).")
    return 0


if __name__ == "__main__":
    code = run(sys.argv[1:])
    if getattr(sys, "frozen", False):
        input("\nPress Enter to close.")
    sys.exit(code)
