"""Per-model build configs in models/*.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def load_all(models_dir: Path = MODELS_DIR) -> dict[str, dict]:
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted(models_dir.glob("*.yaml"))}


def by_sysex_id(model_id: int, models_dir: Path = MODELS_DIR) -> tuple[str, dict] | None:
    for key, cfg in load_all(models_dir).items():
        if cfg.get("sysex_model_id") == model_id:
            return key, cfg
    return None
