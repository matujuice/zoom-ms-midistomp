"""MIDISTOMP-builder: drop Zoom's official MS-70CDR 2.10 updater on this program
and it writes the MIDISTOMP updater next to it.

Same output as `zoomms build` with the patch set (docs/flashing.md).
Refuses any file that is not the stock updater (sha256 in models/ms70cdr.yaml).
Frozen into MIDISTOMP-builder-Windows.exe and MIDISTOMP-builder-Mac-* by
.github/workflows/builder.yml; neither holds Zoom code, each user brings Zoom's updater.
The MS-50G build is frozen at tag v1.1; v1.2 and v2.0 are built from the MS-70CDR 2.10 OS.

Also takes Zoom's Mac updater (ZOOM MS-70CDR v2.10 Updater.app) and then writes
MIDISTOMP V2.0 Updater.app, same as `zoomms build-mac`. On a Mac it then signs
that app for this Mac (xattr + ad-hoc codesign), so it opens with a double-click.
Started with no file (a double-click on the Mac), it asks for the path: the user
drags the app into the Terminal window.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import shlex
import subprocess
import sys
from pathlib import Path

from zoomms import cli, macapp, models

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
NAME = "MIDISTOMP V2.0.4.1"
BASE = ["version-2.0", "boot-logo", "midi-cc", "midi-clock", "midi-settings", "tempo-hold", "scroll"]   # the v1.2 set
PATCHES = BASE + ["looper", "mixer-m2", "diag", "dsp-limit", "fx-category", "pc-force-reload", "sysex-fx-slots", "identity-tag"]   # looper, then mixer-m2, then diag; m0-probe stays test-only
OUT_NAME = "MIDISTOMP V2.0 Updater.exe"
OUT_NAME_MAC = "MIDISTOMP V2.0 Updater.app"
OUT_NAME_OC = "MIDISTOMP V2.0 Updater (360MHz OC).exe"
OUT_NAME_OC_MAC = "MIDISTOMP V2.0 Updater (360MHz OC).app"
TITLE_MAC = "MIDISTOMP V2.0 Updater"        # the Mac title can't be longer than Zoom's 27 characters
TITLE_OC_MAC = "MIDISTOMP V2.0 OC Updater"
PEDALS = [("ms70cdr", "MS-70CDR"), ("ms60b", "MS-60B"), ("ms50g", "MS-50G")]   # first is the default


def identity_tag(name: str = NAME) -> str:
    """The identity reply's 4 version bytes: "M" + the version digits ("V2.0.1" -> "M201").
    A 4th fix number (V2.0.4.1) keeps x.y.z's tag: a fix changes nothing editors read."""
    digits = "".join(re.findall(r"\d", name.rsplit("V", 1)[-1]))
    if len(digits) not in (3, 4):
        raise ValueError(f"{name}: the identity tag needs a 3-digit version (x.y.z, one digit each)")
    return "M" + digits[:3]


def build(updater: Path, out: Path, mac: bool = False, cpu: str | None = None, pedal: str = "ms70cdr") -> int:
    """cpu: an overclock patch (e.g. "360f" -> patches/cpu-360f.yaml); None keeps stock 300 MHz.
    pedal: whose model byte the pedal will report (models/*.yaml key)."""
    argv = ["build-mac" if mac else "build", str(updater), "--build-id", "ms70cdr-2.10", "--out", str(out),
            "--stamp", f"version={NAME.split()[-1]}",   # SYSTEM page shows the full V2.0.3; boot and menu stay V2.0
            "--pedal", pedal]
    if mac:
        argv += ["--title", TITLE_OC_MAC if cpu else TITLE_MAC]
    with tempfile.TemporaryDirectory() as tmp:
        for p in PATCHES + ([f"cpu-{cpu}"] if cpu else []):
            path = ROOT / "patches" / f"{p}.yaml"
            if p == "identity-tag":  # the tag follows NAME, so it never goes stale
                text = path.read_text(encoding="utf-8")
                assert 'data: "4d323031"' in text, "identity-tag.yaml data line changed"
                text = text.replace('data: "4d323031"', f'data: "{identity_tag().encode().hex()}"')
                path = Path(tmp) / path.name
                path.write_text(text, encoding="utf-8")
            argv += ["--patch", str(path)]
        return cli.main(argv)


def sign_for_this_mac(app: Path) -> bool:
    """The patched app no longer matches Zoom's signature; sign it ad hoc for this Mac."""
    try:
        subprocess.run(["xattr", "-cr", str(app)], check=True)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ask_path() -> list[str]:
    """Started without a file (double-click on a Mac): ask for it."""
    print("Drag Zoom's MS-70CDR v2.10 updater (the .app) onto this window, then press Enter:")
    try:
        line = input().strip()
        return shlex.split(line) if line else []  # Terminal pastes the path shell-escaped
    except (EOFError, ValueError):
        return []


def ask_pedal() -> str | None:
    """Which pedal the updater is for: its model byte. Enter keeps the MS-70CDR."""
    print("\nWhich pedal will you flash?")
    for i, (_, name) in enumerate(PEDALS, 1):
        print(f"  {i}) {name}" + ("  (press Enter)" if i == 1 else ""))
    try:
        line = input().strip()
    except EOFError:
        line = ""
    if line in ("", "1", "2", "3"):
        return PEDALS[int(line or 1) - 1][0]
    print(f"{line!r} is not 1, 2 or 3. Nothing was written.")
    return None


def out_name(name: str, pedal: str) -> str:
    """The pedal goes in the file name, so an updater can't be mixed up later; the MS-70CDR keeps today's names."""
    return name if pedal == PEDALS[0][0] else name.replace(" Updater", f" {dict(PEDALS)[pedal]} Updater")


def run(args: list[str]) -> int:
    if not args and getattr(sys, "frozen", False) and sys.platform == "darwin":
        args = ask_path()
    if len(args) != 1:
        print(f"{NAME} builder\n\nDrag Zoom's official MS-70CDR v2.10 updater "
              "(ZOOM MS-70CDR v2.10 Updater.exe) onto this program.\n"
              "On a Mac, open this program and drag Zoom's Mac updater "
              "(ZOOM MS-70CDR v2.10 Updater.app) into its window instead.")
        return 1
    updater = Path(args[0].rstrip("/"))
    mac = updater.suffix == ".app"
    model = models.load_all(ROOT / "models")["ms70cdr"]
    want = model["stock_mac_updater_sha256" if mac else "stock_updater_sha256"]
    try:
        got = hashlib.sha256((macapp.executable(updater) if mac else updater).read_bytes()).hexdigest()
    except OSError as e:
        print(f"Cannot read {updater}: {e}")
        return 1
    if got != want:
        print(f"{updater.name} is not Zoom's official MS-70CDR v2.10 updater.\n"
              f"sha256 {got}\nexpected {want}\nNothing was written.")
        return 1
    pedal = ask_pedal() if getattr(sys, "frozen", False) else PEDALS[0][0]
    if pedal is None:
        return 1
    # Two files from one drag: stock 300 MHz, and an opt-in 360 MHz overclock
    # build for pedals that have been tested at that clock (70CDR, 60B).
    builds = [(updater.with_name(out_name(OUT_NAME_MAC if mac else OUT_NAME, pedal)), None),
              (updater.with_name(out_name(OUT_NAME_OC_MAC if mac else OUT_NAME_OC, pedal)), "360f")]
    for out, cpu in builds:
        if mac and out.exists():
            print(f"{out} already exists; move it away first. Nothing was written.")
            return 1
    done = []
    for out, cpu in builds:
        try:
            failed = build(updater, out, mac, cpu, pedal)
        except ValueError as e:
            print(f"error: {e}")
            failed = 1
        if failed:
            print(f"Done: {done[0]}\nThe {out.name} build failed; only the one above was written." if done
                  else "Build failed, nothing usable was written.")
            return 1
        if mac:
            sign = f'  xattr -cr "{out}"\n  codesign --force --deep --sign - "{out}"'
            if sys.platform != "darwin":
                print(f"\nOn the Mac, sign it before opening it:\n{sign}")
            elif sign_for_this_mac(out):
                print(f"\nSigned {out.name} for this Mac.")
            else:
                print(f"\nCould not sign it. In Terminal run:\n{sign}")
        done.append(out)
    print(f"\nDone: {done[0]} (for the {dict(PEDALS)[pedal]})\nAlso built: {done[1]} (360 MHz overclock, only on a pedal tested at that clock)"
          "\nFlash the one you want in update mode (see the MIDISTOMP user guide).")
    return 0


if __name__ == "__main__":
    try:
        code = run(sys.argv[1:])
    except Exception:  # e.g. a write fails: show it before the window closes
        import traceback
        traceback.print_exc()
        code = 1
    if getattr(sys, "frozen", False):
        input("\nPress Enter to close.")
    sys.exit(code)
