from __future__ import annotations

import json
from pathlib import Path

import yaml

REQUIRED_MODES = {"cheap_triage", "verify", "escalate", "quarantine", "reject", "close"}
REQUIRED_CONTROLS = {
    "mathematically_constructable",
    "random_routing_seed",
    "margin_baseline",
    "trivial_baseline",
    "no_dopamine_ablation",
    "overactivation_regime",
}


def _frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    raw = text[4:end]
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


def validate_contract(config_path: Path, contract_path: Path) -> list[str]:
    errors: list[str] = []
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    text = contract_path.read_text(encoding="utf-8")
    meta = _frontmatter(text)

    if set(cfg.get("modes", {}).keys()) != REQUIRED_MODES:
        errors.append("modes must exactly match required set")
    if set(cfg.get("negative_controls", {}).keys()) != REQUIRED_CONTROLS:
        errors.append("negative controls must be complete and executable")
    w = cfg["priority_gate"]["weights"]
    if abs(sum(float(v) for v in w.values()) - 1.0) > 1e-9:
        errors.append("weights must sum to 1.0")
    if meta.get("semantics") != "non-truth_routing":
        errors.append("frontmatter semantics must be non-truth_routing")
    return errors


def main() -> int:
    errors = validate_contract(Path("configs/dopa_closure_v2/allocator.yaml"), Path("docs/experiments/DOPA_CLOSURE_V2_CONSTRUCT_CONTRACT.md"))
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
