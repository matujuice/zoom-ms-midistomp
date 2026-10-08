"""zoomms command line. Nothing here talks to a pedal except `identify`, which only reads."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from . import ais, asm, flash, models, parts, patcher, updater, zdl


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
    free, stale = updater.free_blocks(fw)
    print(f"free        {free} data blocks (~{free * updater.PAYLOAD // 1024} KiB)")
    for p in fw.problems:
        print(f"PROBLEM {p}")
    return 1 if fw.problems else 0


def cmd_updater_parts(args) -> int:
    found = parts.find_parts(args.updater)
    for p in found:
        h = hashlib.sha256(parts.read_part(args.updater, p)).hexdigest()[:16]
        print(f"BIN/{p.resource_id:<4} {p.role:<16} offset 0x{p.offset:07X} {p.size:>8} B  {p.kind:<18} sha256 {h}")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for p in found:
            (out / f"{p.resource_id}_{p.role.replace(' ', '_')}.bin").write_bytes(parts.read_part(args.updater, p))
        print(f"wrote {len(found)} parts to {out}")
    return 0


def cmd_ais(args) -> int:
    img = ais.parse(Path(args.image).read_bytes())
    print("\n".join(img.log))
    print(f"entry 0x{img.entry:08X}, {sum(len(s.data) for s in img.sections)} bytes in {len(img.sections)} sections")
    if args.elf:
        Path(args.elf).write_bytes(ais.to_elf(img))
        print(f"wrote {args.elf}; disassemble with tic6x-elf-objdump -d")
    return 0


def cmd_build(args) -> int:
    stock = Path(args.updater).read_bytes()
    os_part = next(p for p in parts.find_parts(args.updater) if p.resource_id == 129)
    original = parts.read_part(args.updater, os_part)
    img = ais.parse(original)
    for patch_path in args.patch:
        patch = patcher.load(patch_path)
        try:
            lines = patcher.apply(img, patch, args.build_id)
        except patcher.PatchError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        for line in lines:
            print(f"{patch['name']}: {line}")
    new_os = ais.build_part(img, original)
    exe = flash.build_updater(args.updater, new_os, skip_boot=not args.keep_boot_steps)

    # Re-read what we are about to write and check it.
    check = ais.parse(exe[os_part.offset:os_part.offset + os_part.size])
    assert [s.addr for s in check.sections] == [s.addr for s in img.sections]
    assert check.entry == ais.parse(original).entry
    assert exe[os_part.offset + os_part.size - 32:os_part.offset + os_part.size] == original[-32:]
    outside = [i for i in range(min(len(stock), len(exe))) if stock[i] != exe[i]
               and not os_part.offset <= i < os_part.offset + os_part.size]
    changed_os = sum(1 for a, b in zip(original, new_os) if a != b)
    print(f"OS bytes changed: {changed_os}; other bytes changed: {len(outside)} "
          f"(flash script and PE header); Zoom's signature removed ({len(stock) - len(exe)} B)")
    print("flash steps: " + "; ".join(s.describe() for s in flash.find_script(exe)))
    Path(args.out).write_bytes(exe)
    print(f"wrote {args.out}  sha256 {hashlib.sha256(exe).hexdigest()}")
    return 0


def cmd_asm(args) -> int:
    code = asm.assemble(args.source, int(args.addr, 0))
    print(f"{len(code)} B at {args.addr}")
    print(code.hex())
    return 0


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
    diffs = updater.diff_blocks(fw.image, rebuilt)
    free, stale = updater.free_blocks(fw)
    print(f"live file system: {len(fw.files)} files; {free} free data blocks, {stale} holding stale data (kept as-is)")
    if fw.problems:
        print("\n".join(f"PROBLEM {p}" for p in fw.problems))
    if not diffs:
        print("round trip exact: the live file system is fully understood")
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
    p = sub.add_parser("updater-parts", help="list (and optionally extract) bootloader, OS, patches and file system")
    p.add_argument("updater")
    p.add_argument("--out")
    p.set_defaults(func=cmd_updater_parts)
    p = sub.add_parser("build", help="build a modified updater from a stock one plus patch files")
    p.add_argument("updater", help="stock official updater .exe")
    p.add_argument("--patch", action="append", default=[], help="patch file; omit to rebuild the stock OS")
    p.add_argument("--build-id", default="", help="e.g. ms50g-3.10, used by address-specific patches")
    p.add_argument("--out", required=True)
    p.add_argument("--keep-boot-steps", action="store_true",
                   help="also rewrite the bootloader like the stock updater does (not recommended)")
    p.set_defaults(func=cmd_build)
    p = sub.add_parser("ais", help="decode a TI AIS boot image (bootloader or main OS part)")
    p.add_argument("image")
    p.add_argument("--elf", help="also write an ELF for tic6x-elf-objdump")
    p.set_defaults(func=cmd_ais)
    p = sub.add_parser("asm", help="assemble asm/*.S at an address and print the bytes (needs tic6x binutils)")
    p.add_argument("source")
    p.add_argument("--addr", required=True)
    p.set_defaults(func=cmd_asm)
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
