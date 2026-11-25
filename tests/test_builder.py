import pytest
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("builder", Path(__file__).parent.parent / "scripts" / "midistomp_builder.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_refuses_other_files(tmp_path):
    f = tmp_path / "x.exe"
    f.write_bytes(b"not zoom")
    assert builder.run([str(f)]) == 1
    assert not (tmp_path / builder.OUT_NAME).exists()
    assert not (tmp_path / builder.OUT_NAME_OC).exists()


def test_patch_files_exist():
    assert all((builder.ROOT / "patches" / f"{p}.yaml").exists() for p in builder.PATCHES)


def test_release_sections_do_not_overlap():
    from zoomms import patcher
    spans = sorted((s["addr"], s["addr"] + len(bytes.fromhex("".join(s["data"].split()))), p)
                   for p in builder.PATCHES
                   for s in patcher.load(builder.ROOT / "patches" / f"{p}.yaml").get("section", []))
    for (_, end, a), (start, _, b) in zip(spans, spans[1:]):
        assert end <= start, f"{a} and {b} overlap at 0x{start:08X}"


def test_refuses_other_mac_apps(tmp_path):
    app = tmp_path / "x.app"
    exe = app / "Contents" / "MacOS" / "EFX Updater"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"not zoom")
    assert builder.run([str(app)]) == 1
    assert not (tmp_path / builder.OUT_NAME_MAC).exists()
    assert not (tmp_path / builder.OUT_NAME_OC_MAC).exists()


def test_ask_path_reads_a_dragged_mac_path(monkeypatch):
    # Terminal pastes a dragged app shell-escaped, with a trailing space
    monkeypatch.setattr("builtins.input", lambda: r"/Users/me/Downloads/ZOOM\ MS-70CDR\ v2.10\ Updater.app ")
    assert builder.ask_path() == ["/Users/me/Downloads/ZOOM MS-70CDR v2.10 Updater.app"]
    monkeypatch.setattr("builtins.input", lambda: "")
    assert builder.ask_path() == []


def test_identity_tag_follows_the_version():
    assert builder.identity_tag("MIDISTOMP V2.0.1") == "M201"
    assert builder.identity_tag("MIDISTOMP V2.1.0") == "M210"
    assert builder.identity_tag("MIDISTOMP V2.0.4.1") == "M204"
    with pytest.raises(ValueError):
        builder.identity_tag("MIDISTOMP V2.1")


def test_feature_dependencies_json_matches_release():
    import json
    d = json.loads((builder.ROOT / "docs" / "dev" / "feature-dependencies.json").read_text())
    assert d["order"] == builder.PATCHES == list(d["patches"])
    for p, v in d["patches"].items():   # every need is applied earlier
        assert all(d["order"].index(n) < d["order"].index(p) for n in v["needs"] + v["optional"]), p


def test_mac_titles_fit_zooms(monkeypatch, tmp_path):
    # Zoom's Mac title "ZOOM MS-70CDR v2.10 Updater" is 27 characters; ours is written over it
    zoom = len("ZOOM MS-70CDR v2.10 Updater")
    assert len(Path(builder.OUT_NAME_MAC).stem) <= zoom and len(builder.TITLE_OC_MAC) <= zoom
    seen = []
    monkeypatch.setattr(builder.cli, "main", lambda argv: seen.append(argv) or 0)
    builder.build(tmp_path / "z.app", tmp_path / builder.OUT_NAME_OC_MAC, mac=True, cpu="360f")
    builder.build(tmp_path / "z.app", tmp_path / builder.OUT_NAME_MAC, mac=True)
    title = lambda argv: argv[argv.index("--title") + 1]
    assert title(seen[0]) == builder.TITLE_OC_MAC and title(seen[1]) == builder.TITLE_MAC


def test_pedal_choice(monkeypatch):
    for typed, want in (("", "ms70cdr"), ("2", "ms60b"), ("3", "ms50g"), ("x", None)):
        monkeypatch.setattr("builtins.input", lambda: typed)
        assert builder.ask_pedal_typed() == want
    assert builder.out_name(builder.OUT_NAME_OC_MAC, "ms70cdr") == builder.OUT_NAME_OC_MAC
    assert builder.out_name(builder.OUT_NAME_OC, "ms50g") == "MIDISTOMP V2.0 MS-50G Updater (360MHz OC).exe"
    assert {k for k, _ in builder.PEDALS} == set(builder.models.load_all(builder.ROOT / "models"))


def test_set_pedal_writes_only_the_model_byte():
    from zoomms import cli
    stock = bytes(0x2C00) + b"\x61" + bytes(0x3FF)
    assert cli._set_pedal(stock, None, None) is None and cli._set_pedal(stock, None, "ms70cdr") is None
    new = cli._set_pedal(stock, None, "ms50g")
    assert new[cli.MODEL_AT] == 0x58 and new[:cli.MODEL_AT] == stock[:cli.MODEL_AT] and new[cli.MODEL_AT + 1:] == stock[cli.MODEL_AT + 1:]
    assert cli._set_pedal(stock, stock[:5] + b"x" + stock[6:], "ms60b")[:6] == stock[:5] + b"x"   # keeps patch changes
    with pytest.raises(ValueError):
        cli._set_pedal(bytes(0x3000), None, "ms50g")   # byte isn't a model id: wrong file or offset
