from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REQUIRED_MODES = {"cheap_triage", "verify", "escalate", "quarantine", "reject", "close"}
REQUIRED_CONTROL_KEYS = {
    "mathematically_constructable",
    "random_routing_seed",
    "margin_baseline",
    "trivial_baseline",
    "no_dopamine_ablation",
    "overactivation_regime",
}


def validate_config(path: Path) -> list[str]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    w = cfg["priority_gate"]["weights"]
    if abs(sum(float(v) for v in w.values()) - 1.0) > 1e-9:
        errors.append("weights must sum to 1.0")
    th = cfg["priority_gate"]["thresholds"]
    if not (th["triage"] <= th["verify"] <= th["escalate"]):
        errors.append("thresholds must satisfy triage <= verify <= escalate")
    costs = cfg["budget"]["action_costs"]
    if any(float(v) <= 0 for v in costs.values()):
        errors.append("all action costs must be positive")
    if set(cfg["modes"].keys()) != REQUIRED_MODES:
        errors.append("modes set mismatch")
    controls = cfg["negative_controls"]
    if set(controls.keys()) != REQUIRED_CONTROL_KEYS:
        errors.append("negative control keys mismatch")
    mod = importlib.import_module("core.eai.dopa_controls")
    if not hasattr(mod, "run_controls"):
        errors.append("missing executable control binding run_controls")
    for k, v in cfg["construct_validity_gate"].items():
        if not isinstance(v, bool) or not v:
            errors.append(f"construct_validity_gate.{k} must be true")
    return errors


def main() -> int:
    errors = validate_config(Path("configs/dopa_closure_v2/allocator.yaml"))
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
