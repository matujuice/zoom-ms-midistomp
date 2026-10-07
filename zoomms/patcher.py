"""Apply patch files (patches/*.yaml) to a main OS AIS image.

Patch kinds supported so far:

    replace:   - find: "text"  with: "text"  count: N
        Same-length byte replacement inside loaded sections. Must match exactly
        `count` times, so a patch written once works on every model's build
        or fails loudly.
    write:     - model: ms50g-3.10  addr: 0x...  expect: "hex"  data: "hex"
        Raw write at an address for one specific OS build; `expect` must match.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import ais


class PatchError(ValueError):
    pass


def _bytes(v) -> bytes:
    return v.encode("latin-1") if isinstance(v, str) else bytes(v)


def apply(img: ais.AisImage, patch: dict, build_id: str) -> list[str]:
    log = []
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
        expect, data = bytes.fromhex(w["expect"]), bytes.fromhex(w["data"])
        if img.read(w["addr"], len(expect)) != expect:
            raise PatchError(f"{patch['name']}: bytes at 0x{w['addr']:08X} are not the expected ones")
        img.write(w["addr"], data)
        log.append(f"write 0x{w['addr']:08X} {len(data)} B")
    if not log:
        raise PatchError(f"{patch['name']}: nothing applied for {build_id}")
    return log


def load(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())
