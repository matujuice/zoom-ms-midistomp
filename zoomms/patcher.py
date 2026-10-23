"""Apply patch files (patches/*.yaml) to a main OS AIS image.

Patch kinds supported so far:

    replace:   - find: "text"  with: "text"  count: N
        Same-length byte replacement inside loaded sections. Must match exactly
        `count` times, so a patch written once works on every model's build
        or fails loudly.
    write:     - model: ms50g-3.10  addr: 0x...  expect: "hex"  data: "hex"
        Raw write at an address for one specific OS build; `expect` must match
        (or one of a list, where another patch may have chained the same hook).
    section:   - model: ms50g-3.10  addr: 0x...  data: "hex"  source: asm/...
        New code or data loaded by the boot image as an extra section (into RAM
        nothing else uses). `source` names the assembly it was built from;
        tests check the bytes still match it. Optional `stamp: {key: offset}`:
        16-byte "<key>" placeholders the build fills with text (version,
        commit, date, label: see `zoomms build --stamp`).
    bin133:    - model: ms50g-3.10  offset: 0  expect_sha256: "..."  data: "hex"
        Overwrite bytes of updater part BIN/133 (the boot logo), not the OS.
        `expect_sha256` is the hash of the stock bytes being replaced, so no
        Zoom data needs to live in the repo.

A patch may list `builds: [...]`; building it for any other OS build fails
with a clear message instead of silently doing nothing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from . import ais


class PatchError(ValueError):
    pass


def _bytes(v) -> bytes:
    return v.encode("latin-1") if isinstance(v, str) else bytes(v)


STAMP_SIZE = 16


def stamp_placeholder(key: str) -> bytes:
    return f"<{key}>".encode().ljust(STAMP_SIZE, b"\0")


def stamp_section(sec: dict, stamp: dict | None, name: str = "patch") -> bytes:
    """The section's bytes with its `stamp:` fields ({key: offset}) filled from
    `stamp` ({key: text}): 16-byte zero-padded ASCII, at most 15 characters.
    Keys missing from `stamp` keep their placeholder."""
    data = bytearray.fromhex(sec["data"])
    for key, off in sec.get("stamp", {}).items():
        if data[off:off + STAMP_SIZE] != stamp_placeholder(key):
            raise PatchError(f"{name}: no <{key}> placeholder at section +{off}")
        if stamp and key in stamp:
            text = str(stamp[key]).encode("ascii")[:STAMP_SIZE - 1]
            data[off:off + STAMP_SIZE] = text.ljust(STAMP_SIZE, b"\0")
    return bytes(data)


def apply(img: ais.AisImage, patch: dict, build_id: str, stamp: dict | None = None) -> list[str]:
    log = []
    if "builds" in patch and build_id not in patch["builds"]:
        raise PatchError(f"{patch['name']}: only written for {', '.join(patch['builds'])}, not {build_id or 'this build'}")
    for r in patch.get("replace", []):
        find, new = _bytes(r["find"]), _bytes(r["with"])
        if len(find) != len(new):
            raise PatchError(f"{patch['name']}: replace must keep length ({find!r} -> {new!r})")
        hits = []
        for s in img.sections:
            i = s.data.find(find)
            while i >= 0:
                hits.append(s.addr + i)
                i = s.data.find(find, i + 1)
        if len(hits) != r.get("count", 1):
            raise PatchError(f"{patch['name']}: {find!r} found {len(hits)} times, expected {r.get('count', 1)}")
        for a in hits:
            img.write(a, new)
            log.append(f"replace 0x{a:08X} {find!r} -> {new!r}")
    for w in patch.get("write", []):
        if w["model"] != build_id:
            continue
        data = bytes.fromhex(w["data"])
        expects = w["expect"] if isinstance(w["expect"], list) else [w["expect"]]   # a list: any of them
        if not any(img.read(w["addr"], len(e) // 2) == bytes.fromhex(e) for e in expects):
            raise PatchError(f"{patch['name']}: bytes at 0x{w['addr']:08X} are not the expected ones")
        img.write(w["addr"], data)
        log.append(f"write 0x{w['addr']:08X} {len(data)} B")
    for sec in patch.get("section", []):
        if sec["model"] != build_id:
            continue
        data = stamp_section(sec, stamp, patch["name"])
        try:
            img.add_section(sec["addr"], data)
        except ais.AisError as e:
            raise PatchError(f"{patch['name']}: {e}") from e
        log.append(f"section 0x{sec['addr']:08X} {len(data)} B")
    if not log and not any(b["model"] == build_id for b in patch.get("bin133", [])):
        raise PatchError(f"{patch['name']}: nothing applied for {build_id}")
    return log


def apply_bin133(part: bytearray, patch: dict, build_id: str) -> list[str]:
    log = []
    for b in patch.get("bin133", []):
        if b["model"] != build_id:
            continue
        off, data = b["offset"], bytes.fromhex(b["data"])
        if off + len(data) > len(part):
            raise PatchError(f"{patch['name']}: BIN/133 write past the end of the part")
        if hashlib.sha256(part[off:off + len(data)]).hexdigest() != b["expect_sha256"]:
            raise PatchError(f"{patch['name']}: BIN/133 bytes at {off} are not the expected ones")
        part[off:off + len(data)] = data
        log.append(f"BIN/133 +{off} {len(data)} B")
    return log


def load(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())
