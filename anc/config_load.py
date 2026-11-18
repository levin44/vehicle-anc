from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ANC_DIR = Path(__file__).resolve().parent


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else ANC_DIR / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {cfg_path}")
    return cfg


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    rel = cfg.get(key, "")
    p = Path(rel)
    return p if p.is_absolute() else ANC_DIR / p