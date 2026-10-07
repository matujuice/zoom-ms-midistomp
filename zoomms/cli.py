"""zoomms command line. Every command here is read-only."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from . import models, updater, zdl


def cmd_identify(args) -> int:
    from .midi import identify

    ident = identify(args.port)
    if ident is None:
        print("no identity reply")
        return 1
    match = models.by_sysex_id(ident.family) if ident.manufacturer == 0x52 else None
    label = match[1]["name"] if match else "unknown model"
    print(f"manufacturer 0x{ident.manufacturer:02X}  model 0x{ident.family:02X} ({label})  firmware {ident.version}")
    return 0


def cmd_updater_info(args) -> int:
    data = Path(args.updater).read_bytes()
    fw = updater.parse(data)
    print(f"sha256      {hashlib.sha256(data).hexdigest()}")
    print(f"image       offset 0x{fw.offset:X}, {fw.block_count} blocks, live table at block {fw.table_block}")
    used = sum(len(f.blocks) for f in fw.files)
    print(f"files       {len(fw.files)} using {used} of {fw.block_count - updater.SYS_BLOCKS} data blocks")
    for f in fw.files:
        extra = ""
        if f.name.upper().endswith(".ZDL") and f.content:
            try:
                z = zdl.parse(f.content)
                extra = f"  {z.category} v{z.fx_version}"
            except zdl.ZdlError as e:
                extra = f"  (bad ZDL: {e})"
        print(f"  {f.name:<12} {f.size:>8}{extra}")
    for p in fw.problems:
        print(f"PROBLEM {p}")
    return 1 if fw.problems else 0


def cmd_updater_extract(args) -> int:
    fw = updater.load(args.updater)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in fw.files:
        (out / f.name).write_bytes(f.content)
    print(f"extracted {len(fw.files)} files to {out}")
    return 1 if fw.problems else 0


def cmd_updater_verify(args) -> int:
    fw = updater.load(args.updater)
    rebuilt = updater.rebuild(fw)
    diffs = updater.diff_regions(fw.image, rebuilt)
    if fw.problems:
        print("\n".join(f"PROBLEM {p}" for p in fw.problems))
    if not diffs:
        print("round trip exact: every byte of the image is accounted for")
        return 1 if fw.problems else 0
    print(f"round trip differs in {len(diffs)} of {fw.block_count} blocks: {diffs[:20]}{' ...' if len(diffs) > 20 else ''}")
    return 1


def cmd_zdl_info(args) -> int:
    rc = 0
    for path in args.files:
        try:
            z = zdl.load(path)
        except zdl.ZdlError as e:
            print(f"{path}: {e}")
            rc = 1
            continue
        machine = "C6000" if z.elf_machine == zdl.EM_TI_C6000 else f"machine {z.elf_machine}"
        print(f"{Path(path).name:<16} {z.category:<12} v{z.fx_version:<6} sort {z.sort_index:>3}  elf {len(z.elf)} B {machine}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zoomms", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("identify", help="ask the pedal for its model and firmware version")
    p.add_argument("--port")
    p.set_defaults(func=cmd_identify)
    p = sub.add_parser("updater-info", help="list files inside an official updater")
    p.add_argument("updater")
    p.set_defaults(func=cmd_updater_info)
    p = sub.add_parser("updater-extract", help="extract files from an official updater")
    p.add_argument("updater")
    p.add_argument("out")
    p.set_defaults(func=cmd_updater_extract)
    p = sub.add_parser("updater-verify", help="check the parser accounts for every byte of the image")
    p.add_argument("updater")
    p.set_defaults(func=cmd_updater_verify)
    p = sub.add_parser("zdl-info", help="show ZDL header fields")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_zdl_info)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
