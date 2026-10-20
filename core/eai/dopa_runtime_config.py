"""Runtime-read, hash-bound DOPA configuration with finite numeric invariants."""

from __future__ import annotations

import hashlib
import json
import math
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


def _require_finite_numbers(value: Any, pointer: str = "$") -> None:
    """YAML accepts .nan/.inf; JSON Schema alone is not a finite-number check."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite_number:{pointer}")
    if isinstance(value, dict):
        for key, nested in value.items():
            _require_finite_numbers(nested, f"{pointer}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _require_finite_numbers(nested, f"{pointer}[{index}]")


def _validate_routing_contract(cfg: dict[str, Any]) -> None:
    """Reject missing thresholds/costs before any filesystem side effects."""
    gate = cfg["priority_gate"]
    t = gate["thresholds"]
    required_t = (
        "triage",
        "verify",
        "escalate",
        "reject_evidence_risk",
        "close_evidence_risk_max",
    )
    for name in required_t:
        if name not in t or not isinstance(t[name], (int, float)):
            raise ValueError(f"missing_or_invalid_threshold:{name}")
        if isinstance(t[name], bool) or not 0 <= t[name] <= 1:
            raise ValueError(f"threshold_out_of_unit_interval:{name}")
    if not (t["triage"] <= t["verify"] <= t["escalate"]):
        raise ValueError("routing_thresholds_out_of_order")
    if not 0 <= gate["load_center"] <= 1:
        raise ValueError("load_center_out_of_bounds")
    costs = cfg["budget"]["action_costs"]
    for name in ("cheap_triage", "verify", "escalate", "quarantine", "reject"):
        if name not in costs:
            raise ValueError(f"missing_action_cost:{name}")


def load_and_validate_config(config_path: Path, schema_path: Path) -> Result[LoadedConfig]:
    try:
        # Single-byte snapshot prevents hash/payload TOCTOU within the loader.
        raw = config_path.read_bytes()
        cfg = yaml.safe_load(raw.decode("utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _require_finite_numbers(cfg)
        validate(cfg, schema)
        if not isinstance(cfg, dict):
            raise ValueError("payload_not_object")
        _validate_routing_contract(cfg)
        return Ok(LoadedConfig(payload=cfg, config_hash=hashlib.sha256(raw).hexdigest()))
    except (OSError, ValueError, TypeError, UnicodeError, KeyError) as exc:
        return Err(f"config_invalid:{exc}")
    except Exception as exc:
        # jsonschema.ValidationError, YAML parser failures etc. fail closed.
        return Err(f"config_invalid:{exc}")
