"""Evidence-branch split — Task 5 of the γ-program remediation protocol.

Splits the HRV evidence into two independent branches, each tracked
with its own claim_status so a failure in one branch never silently
propagates credit to the other.

  Branch A — spectral:    Welch PSD, aperiodic-exponent fits, LF/HF
                           structure. Claims in this branch are about
                           frequency-domain regularity (Task Force 1996).

  Branch B — nonlinear:   DFA α₁/α₂, Poincaré SD1/SD2, Sample entropy,
                           MFDFA Δh (when computed). Claims here are
                           about scaling / fractal structure (Peng 1995,
                           Kantelhardt 2002, Richman & Moorman 2000).

No combined score is licensed until BOTH branches converge on
external validation AND the Task 6 null suite passes for each branch
*independently*.

The branch registry lives at
``evidence/gamma_branches/branches.yaml`` and is read at import time;
any code that reports γ-program evidence must pass through
:func:`branch_for_metric` so misclassification is detectable.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "Branch",
    "BranchRegistry",
    "branch_for_metric",
    "load_branch_registry",
    "roll_up_from_baseline",
]

_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "evidence" / "gamma_branches" / "branches.yaml"
)

BranchName = Literal["branch_a_spectral", "branch_b_nonlinear"]

# Canonical metric → branch map. Every metric produced by
# :mod:`tools.hrv.baseline_panel` lands on exactly one branch here;
# double-counting is forbidden.
_METRIC_TO_BRANCH: dict[str, BranchName] = {
    # Spectral — Branch A
    "total_power_ms2": "branch_a_spectral",
    "lf_power_ms2": "branch_a_spectral",
    "hf_power_ms2": "branch_a_spectral",
    "lf_hf_ratio": "branch_a_spectral",
    # Time-domain variance is a surface of the spectral integral (Parseval)
    "sdnn_ms": "branch_a_spectral",
    # Non-linear — Branch B
    "rmssd_ms": "branch_b_nonlinear",
    "dfa_alpha1": "branch_b_nonlinear",
    "dfa_alpha2": "branch_b_nonlinear",
    "poincare_sd1_ms": "branch_b_nonlinear",
    "poincare_sd2_ms": "branch_b_nonlinear",
    "sample_entropy": "branch_b_nonlinear",
}


@dataclasses.dataclass(frozen=True)
class Branch:
    name: BranchName
    metrics: tuple[str, ...]
    claim_status: str
    description: str


@dataclasses.dataclass(frozen=True)
class BranchRegistry:
    schema_version: int
    branches: dict[BranchName, Branch]

    def metrics_for(self, branch: BranchName) -> tuple[str, ...]:
        return self.branches[branch].metrics


def branch_for_metric(metric: str) -> BranchName:
    if metric not in _METRIC_TO_BRANCH:
        raise KeyError(f"metric {metric!r} is not assigned to an evidence branch")
    return _METRIC_TO_BRANCH[metric]


def _parse_yaml(text: str) -> dict[str, Any]:
    """Minimal parser for the branches YAML — regular shape, no deps."""

    out: dict[str, Any] = {"branches": {}}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if stripped.startswith("schema_version:"):
            out["schema_version"] = int(stripped.split(":", 1)[1].strip())
            i += 1
            continue
        if stripped == "branches:":
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                if not lines[i].strip():
                    i += 1
                    continue
                name = lines[i].strip().rstrip(":")
                block: dict[str, Any] = {}
                i += 1
                while i < len(lines) and lines[i].startswith("    "):
                    s = lines[i].strip()
                    if s.startswith("claim_status:"):
                        block["claim_status"] = s.split(":", 1)[1].strip().strip('"')
                    elif s.startswith("description:"):
                        block["description"] = s.split(":", 1)[1].strip().strip('"')
                    elif s.startswith("metrics:"):
                        raw = s.split(":", 1)[1].strip()
                        raw = raw.strip("[]")
                        block["metrics"] = tuple(
                            c.strip().strip("\"'") for c in raw.split(",") if c.strip()
                        )
                    i += 1
                out["branches"][name] = block
            continue
        i += 1
    return out


def load_branch_registry(path: Path = _REGISTRY_PATH) -> BranchRegistry:
    data = _parse_yaml(path.read_text(encoding="utf-8"))
    branches: dict[BranchName, Branch] = {}
    for name_str, block in data["branches"].items():
        name: BranchName = name_str  # type: ignore[assignment]
        branches[name] = Branch(
            name=name,
            metrics=tuple(block.get("metrics", ())),
            claim_status=block.get("claim_status", "hypothesized"),
            description=block.get("description", ""),
        )

    # Cross-check: YAML metric assignment must match the module map.
    for br in branches.values():
        for m in br.metrics:
            if _METRIC_TO_BRANCH.get(m) != br.name:
                raise ValueError(
                    f"branch registry disagrees with module map: "
                    f"{m!r} assigned to {br.name} in YAML but to "
                    f"{_METRIC_TO_BRANCH.get(m)} in code"
                )
    return BranchRegistry(schema_version=int(data["schema_version"]), branches=branches)


def roll_up_from_baseline(
    baseline_summary: dict[str, Any],
    registry: BranchRegistry,
) -> dict[BranchName, dict[str, Any]]:
    """Partition the baseline cohort means by branch.

    ``baseline_summary`` is the contents of
    ``results/hrv_baseline/panel_summary.json`` (Task 3). The roll-up
    produces, per branch:
      - list of metric names on this branch
      - per-cohort mean (± std) for every metric on this branch
      - claim_status copied from the registry for downstream gating
    """

    out: dict[BranchName, dict[str, Any]] = {}
    per_cohort = baseline_summary["per_cohort"]
    for name, branch in registry.branches.items():
        cohort_view: dict[str, dict[str, dict[str, float]]] = {}
        for cohort, cohort_block in per_cohort.items():
            metrics = cohort_block["metrics"]
            cohort_view[cohort] = {m: metrics[m] for m in branch.metrics if m in metrics}
        out[name] = {
            "claim_status": branch.claim_status,
            "description": branch.description,
            "metrics": list(branch.metrics),
            "per_cohort": cohort_view,
        }
    return out


def roll_up_from_blind_validation(
    validation_report_dict: dict[str, Any],
    registry: BranchRegistry,
) -> dict[BranchName, dict[str, Any]]:
    """Per-branch dev AUC / ext AUC aggregate from a Task 8 report.

    We report the *median* absolute Cohen's d and median AUC across
    metrics on each branch — robust summary that a single loud metric
    (e.g. SDNN on Branch A) cannot dominate.
    """

    import statistics

    out: dict[BranchName, dict[str, Any]] = {}
    pm = validation_report_dict["per_metric"]
    for name, branch in registry.branches.items():
        dev_aucs = [pm[m]["development"]["auc"] for m in branch.metrics if m in pm]
        ext_aucs = [pm[m]["external"]["auc"] for m in branch.metrics if m in pm]
        dev_ds = [abs(pm[m]["development"]["cohens_d"]) for m in branch.metrics if m in pm]
        ext_ds = [abs(pm[m]["external"]["cohens_d"]) for m in branch.metrics if m in pm]
        out[name] = {
            "claim_status": branch.claim_status,
            "n_metrics": len(branch.metrics),
            "median_dev_auc": float(statistics.median(dev_aucs)) if dev_aucs else float("nan"),
            "median_ext_auc": float(statistics.median(ext_aucs)) if ext_aucs else float("nan"),
            "median_dev_abs_d": float(statistics.median(dev_ds)) if dev_ds else float("nan"),
            "median_ext_abs_d": float(statistics.median(ext_ds)) if ext_ds else float("nan"),
        }
    return out


def emit_branch_roll_up(
    out_path: Path,
    baseline_summary_path: Path,
    validation_report_path: Path,
) -> dict[str, Any]:
    reg = load_branch_registry()
    base = json.loads(baseline_summary_path.read_text("utf-8"))
    val = json.loads(validation_report_path.read_text("utf-8"))
    report = {
        "schema_version": 1,
        "branches_from_baseline": roll_up_from_baseline(base, reg),
        "branches_from_blind_validation": roll_up_from_blind_validation(val, reg),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
