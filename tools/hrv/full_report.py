"""Publication-grade γ-program run report (Task 10).

Bundles every committed artefact from Tasks 1–9 into a single JSON
so reviewers / replicators have one file to audit:

  * Cohort manifests + SHA-256s (Task 1).
  * Analysis split + hash (Task 2).
  * Baseline panel summary + per-cohort means (Task 3).
  * Canonical stack version (Task 4).
  * Evidence-branch roll-up (Task 5).
  * Null-suite aggregate (Task 6).
  * Outlier-protocol summary (Task 7).
  * Blind-validation dev+ext metrics + frozen thresholds hash (Task 8).
  * State-contrast summary (Task 9).
  * Software version stamps + current git SHA.

The resulting file is committed at
``reports/runs/{timestamp}/full_report.json`` so every run leaves a
durable audit trail. The generator is deterministic: given the same
set of committed artefacts it always produces the same payload
(except the top-level ``run_utc`` timestamp).
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["build_full_report", "write_full_report"]

_REPO = Path(__file__).resolve().parents[2]


def _git_sha() -> str:
    try:
        out = subprocess.run(  # noqa: S603, S607
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "wfdb"):
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ModuleNotFoundError:
            versions[pkg] = "not installed"
    return versions


def build_full_report() -> dict[str, Any]:
    from tools.hrv.canonical_stack import CANONICAL_STACK_VERSION

    manifests_dir = _REPO / "data" / "manifests"
    cohorts = ["nsr2db", "chfdb", "chf2db", "nsrdb"]
    cohort_manifests = {
        c: {
            "path": f"data/manifests/{c}_manifest.json",
            "sha256": _sha256_of(manifests_dir / f"{c}_manifest.json"),
            "data": _load_json(manifests_dir / f"{c}_manifest.json"),
        }
        for c in cohorts
    }

    split_path = _REPO / "config" / "analysis_split.yaml"
    thresholds_path = _REPO / "config" / "thresholds_frozen.yaml"
    baseline_summary_path = _REPO / "results" / "hrv_baseline" / "panel_summary.json"
    null_summary_path = _REPO / "evidence" / "surrogates" / "null_suite_summary.json"
    outlier_summary_path = _REPO / "reports" / "outlier_protocol" / "summary.json"
    validation_path = _REPO / "reports" / "blind_validation" / "report.json"
    branches_path = _REPO / "reports" / "gamma_branches" / "roll_up.json"
    state_contrast_path = _REPO / "reports" / "state_contrast" / "summary.json"
    branch_registry_path = _REPO / "evidence" / "gamma_branches" / "branches.yaml"

    report = {
        "schema_version": 1,
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": _git_sha(),
        "software": _software_versions(),
        "canonical_stack_version": CANONICAL_STACK_VERSION,
        "cohort_manifests": cohort_manifests,
        "analysis_split": {
            "path": "config/analysis_split.yaml",
            "sha256": _sha256_of(split_path),
        },
        "thresholds_frozen": {
            "path": "config/thresholds_frozen.yaml",
            "sha256": _sha256_of(thresholds_path),
        },
        "branch_registry": {
            "path": "evidence/gamma_branches/branches.yaml",
            "sha256": _sha256_of(branch_registry_path),
        },
        "baseline_panel_summary": _load_json(baseline_summary_path),
        "null_suite_summary": _load_json(null_summary_path),
        "outlier_protocol_summary": _load_json(outlier_summary_path),
        "blind_validation_report": _load_json(validation_path),
        "evidence_branches_roll_up": _load_json(branches_path),
        "state_contrast_summary": _load_json(state_contrast_path),
    }
    return report


def write_full_report(out_dir: Path | None = None) -> Path:
    report = build_full_report()
    ts = report["run_utc"].replace(":", "").replace("-", "")
    dest = (out_dir or _REPO / "reports" / "runs") / ts
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "full_report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
