from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import validate

from core.eai.dopa_result import Err, Ok, Result


@dataclass(frozen=True)
class LoadedConfig:
    payload: dict[str, Any]
    config_hash: str


def load_and_validate_config(config_path: Path, schema_path: Path) -> Result[LoadedConfig]:
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(cfg, schema)
    except Exception as exc:
        return Err(f"config_invalid:{exc}")

    if not isinstance(cfg, dict):
        return Err("config_invalid:payload_not_object")

    digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    return Ok(LoadedConfig(payload=cfg, config_hash=digest))
