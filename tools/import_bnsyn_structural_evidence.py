"""Importer: BN-Syn canonical proof bundle → NeoSynaptex structural-evidence JSON.

CLI
---
::

    python -m tools.import_bnsyn_structural_evidence \\
        --bundle PATH \\
        --out evidence/bnsyn_structural_evidence.json

The importer reads a BN-Syn canonical proof bundle directory (the kind
emitted by ``bnsyn run --profile canonical --plot --export-proof``) and
produces a single normalised JSON document carrying ONLY the local
structural-evidence surface defined in
``contracts/bnsyn_structural_evidence.py``.

Bundle layout (required files within ``--bundle PATH``)::

    criticality_report.json     # σ_mean → κ
    avalanche_report.json       # sizes / counts → distribution summary
    avalanche_fit_report.json   # alpha, p_value, validity.verdict
    phase_space_report.json     # coherence_mean
    run_manifest.json           # provenance: artifacts hash dict
    robustness_report.json      # determinism: replay_check.identical

Bundle layout (optional)::

    summary_metrics.json        # ignored by this importer
    envelope_report.json        # ignored by this importer

Fail-closed contract
--------------------
* Missing required file → ``claim_status = NO_ADMISSIBLE_CLAIM``.
* Missing/NaN/inf metric → ``claim_status = NO_ADMISSIBLE_CLAIM``.
* Surrogate not rejected (per the proxy rule in the thresholds YAML)
  → ``claim_status = ARTIFACT_SUSPECTED``.
* Provenance / determinism gates failing → at best
  ``LOCAL_STRUCTURAL_EVIDENCE_ONLY``; this importer NEVER emits
  ``VALIDATED_SUBSTRATE_EVIDENCE`` because that requires a γ-side
  pass which this contract refuses to fabricate (κ ≠ γ).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

# Ensure the repository root is importable when invoked as
# ``python -m tools.import_bnsyn_structural_evidence``. The standard
# ``-m`` invocation from the repo root already handles this; we add
# an explicit fallback for direct ``python tools/import_...`` calls.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.bnsyn_structural_evidence import (  # noqa: E402
    BnSynEvidenceVerdict,
    BnSynStructuralMetrics,
    validate_metrics,
)

__all__ = [
    "main",
    "load_bundle",
    "extract_metrics",
    "compute_verdict",
    "build_output_document",
    "strict_json_sanitize",
    "REQUIRED_FILES",
]


def strict_json_sanitize(value: Any) -> Any:
    """Recursively coerce a value into a strict-JSON-safe shape.

    Non-finite floats (``NaN``, ``+Infinity``, ``-Infinity``) are not part
    of the strict JSON grammar (RFC 8259) and would otherwise be written
    by ``json.dump`` as bare ``NaN`` / ``Infinity`` tokens. The evidence
    ledger MUST stay strict-JSON, so this sanitizer maps every such
    value to ``None`` and walks dicts / lists / tuples in place. Tuples
    are emitted as JSON arrays — Python's ``json`` does the same — but
    keys are coerced to ``str`` defensively so a stray non-string key
    does not crash the writer downstream.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): strict_json_sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_json_sanitize(v) for v in value]
    return value


REQUIRED_FILES: tuple[str, ...] = (
    "criticality_report.json",
    "avalanche_report.json",
    "avalanche_fit_report.json",
    "phase_space_report.json",
    "run_manifest.json",
    "robustness_report.json",
)

_DEFAULT_THRESHOLDS_PATH = _REPO_ROOT / "config" / "bnsyn_structural_thresholds.yaml"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data: Any = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object at top level, got {type(data).__name__}")
    return data


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data: Any = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected YAML mapping at top level")
    return data


def load_bundle(bundle_dir: Path) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    """Load BN-Syn bundle. Return ``(reports, missing_files)``.

    ``reports`` maps the basename of each required file to its parsed
    dict. ``missing_files`` is a tuple of filenames that were not
    found; the caller treats a non-empty tuple as a fail-closed
    condition.
    """
    reports: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for name in REQUIRED_FILES:
        path = bundle_dir / name
        if not path.is_file():
            missing.append(name)
            continue
        try:
            reports[name] = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            missing.append(f"{name} (parse_error: {type(exc).__name__})")
    return reports, tuple(missing)


def _safe_float(value: Any) -> float:
    """Coerce numerics to float; return NaN on missing/invalid input.

    NaN is the canonical "not finite" sentinel that downstream
    validation will catch. Booleans are explicitly rejected (they
    coerce to 0/1 in Python, which would silently corrupt the
    ``kappa`` field).
    """
    if isinstance(value, bool):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    return float("nan")


def extract_metrics(
    reports: dict[str, dict[str, Any]],
    thresholds: dict[str, Any],
) -> BnSynStructuralMetrics:
    """Project the bundle reports onto the canonical structural metrics."""

    crit = reports.get("criticality_report.json", {})
    aval = reports.get("avalanche_report.json", {})
    fit = reports.get("avalanche_fit_report.json", {})
    phase = reports.get("phase_space_report.json", {})

    kappa = _safe_float(crit.get("sigma_mean"))

    # BN-Syn does not currently emit κ CI bounds; honour the contract
    # by surfacing whatever the caller may have appended downstream.
    raw_low = crit.get("sigma_ci_low") if isinstance(crit, dict) else None
    raw_high = crit.get("sigma_ci_high") if isinstance(crit, dict) else None
    kappa_ci_low: float | None = _safe_float(raw_low) if raw_low is not None else None
    kappa_ci_high: float | None = _safe_float(raw_high) if raw_high is not None else None
    # Translate NaN sentinels (from _safe_float on garbage) back to None
    # so downstream "missing CI" stays unambiguous.
    if kappa_ci_low is not None and not math.isfinite(kappa_ci_low):
        kappa_ci_low = None
    if kappa_ci_high is not None and not math.isfinite(kappa_ci_high):
        kappa_ci_high = None

    avalanche_fit_quality = _safe_float(fit.get("p_value"))

    # Build a *minimal* distribution summary. We do NOT copy the raw
    # ``sizes``/``durations`` arrays — those are large and already
    # hashed in the run manifest. The summary's purpose is "does the
    # distribution exist" plus a few headline parameters.
    avalanche_distribution_summary: dict[str, Any] = {}
    if isinstance(aval, dict) and aval:
        avalanche_distribution_summary = {
            "avalanche_count": aval.get("avalanche_count"),
            "size_max": aval.get("size_max"),
            "duration_max": aval.get("duration_max"),
            "size_mean": aval.get("size_mean"),
            "duration_mean": aval.get("duration_mean"),
            "alpha": fit.get("alpha") if isinstance(fit, dict) else None,
            "tau": fit.get("tau") if isinstance(fit, dict) else None,
            "fit_method": fit.get("fit_method") if isinstance(fit, dict) else None,
            "validity_verdict": (
                (fit.get("validity") or {}).get("verdict") if isinstance(fit, dict) else None
            ),
        }

    phase_coherence = _safe_float(phase.get("coherence_mean"))

    # Surrogate-rejection proxy. The proxy mapping is configurable via
    # the thresholds YAML; without an explicit, honest mapping this
    # field MUST stay False so the verdict downgrades.
    surrogate_cfg = thresholds.get("surrogate", {})
    proxy_enabled = bool(surrogate_cfg.get("proxy_from_avalanche_fit", False))
    required_verdict = str(surrogate_cfg.get("required_validity_verdict", ""))
    aval_floor = float(thresholds.get("avalanche", {}).get("fit_quality_floor", 1.0))

    phase_surrogate_rejected = False
    if proxy_enabled and isinstance(fit, dict):
        validity = fit.get("validity")
        verdict = validity.get("verdict") if isinstance(validity, dict) else None
        p_val = _safe_float(fit.get("p_value"))
        if (
            isinstance(verdict, str)
            and verdict == required_verdict
            and math.isfinite(p_val)
            and p_val >= aval_floor
        ):
            phase_surrogate_rejected = True

    return BnSynStructuralMetrics(
        kappa=kappa,
        kappa_ci_low=kappa_ci_low,
        kappa_ci_high=kappa_ci_high,
        avalanche_fit_quality=avalanche_fit_quality,
        avalanche_distribution_summary=avalanche_distribution_summary,
        phase_coherence=phase_coherence,
        phase_surrogate_rejected=phase_surrogate_rejected,
    )


def _provenance_ok(reports: dict[str, dict[str, Any]], thresholds: dict[str, Any]) -> bool:
    cfg = thresholds.get("provenance", {})
    if cfg.get("require_run_manifest", True):
        manifest = reports.get("run_manifest.json")
        if not isinstance(manifest, dict):
            return False
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or len(artifacts) == 0:
            return False
    return True


def _determinism_ok(reports: dict[str, dict[str, Any]], thresholds: dict[str, Any]) -> bool:
    cfg = thresholds.get("provenance", {})
    if not cfg.get("require_replay_identical", True):
        return True
    rb = reports.get("robustness_report.json")
    if not isinstance(rb, dict):
        return False
    replay = rb.get("replay_check")
    if not isinstance(replay, dict):
        return False
    return bool(replay.get("identical", False))


def _local_pass(metrics: BnSynStructuralMetrics, thresholds: dict[str, Any]) -> bool:
    """Local structural pass — see docstring at top of module."""

    kappa_cfg = thresholds.get("kappa", {})
    target = float(kappa_cfg.get("target", 1.0))
    tolerance = float(kappa_cfg.get("tolerance", 0.1))

    kappa_ok_point = math.isfinite(metrics.kappa) and abs(metrics.kappa - target) <= tolerance
    kappa_ok_ci = (
        metrics.kappa_ci_low is not None
        and metrics.kappa_ci_high is not None
        and math.isfinite(metrics.kappa_ci_low)
        and math.isfinite(metrics.kappa_ci_high)
        and metrics.kappa_ci_low <= target <= metrics.kappa_ci_high
    )
    if not (kappa_ok_point or kappa_ok_ci):
        return False

    aval_cfg = thresholds.get("avalanche", {})
    fit_floor = float(aval_cfg.get("fit_quality_floor", 0.0))
    min_count = int(aval_cfg.get("min_avalanche_count", 0))

    if not isinstance(metrics.avalanche_distribution_summary, dict):
        return False
    if len(metrics.avalanche_distribution_summary) == 0:
        return False
    count = metrics.avalanche_distribution_summary.get("avalanche_count")
    if not isinstance(count, (int, float)) or isinstance(count, bool) or count < min_count:
        return False
    if not math.isfinite(metrics.avalanche_fit_quality):
        return False
    if metrics.avalanche_fit_quality < fit_floor:
        return False

    coh_cfg = thresholds.get("phase_coherence", {})
    coh_floor = float(coh_cfg.get("min_value", 0.0))
    if not math.isfinite(metrics.phase_coherence):
        return False
    if metrics.phase_coherence < coh_floor:
        return False
    return bool(metrics.phase_surrogate_rejected)


def compute_verdict(
    metrics: BnSynStructuralMetrics,
    reports: dict[str, dict[str, Any]],
    thresholds: dict[str, Any],
    *,
    gamma_pass: bool | None = None,
) -> BnSynEvidenceVerdict:
    """Compute the fail-closed claim verdict.

    ``gamma_pass`` is supplied by the caller's γ pipeline (None iff
    no γ-side judgement is available). The importer never sets this
    to True from BN-Syn metrics alone — κ is not γ.
    """
    reasons_list: list[str] = []

    validation_reasons = validate_metrics(metrics)
    if validation_reasons:
        return BnSynEvidenceVerdict(
            local_structural_status="MISSING",
            gamma_status="NO_ADMISSIBLE_CLAIM",
            artifact_status="MISSING",
            claim_status="NO_ADMISSIBLE_CLAIM",
            reasons=validation_reasons,
        )

    if not metrics.phase_surrogate_rejected:
        return BnSynEvidenceVerdict(
            local_structural_status="FAIL",
            gamma_status="NO_ADMISSIBLE_CLAIM",
            artifact_status="ARTIFACT_SUSPECTED",
            claim_status="ARTIFACT_SUSPECTED",
            reasons=("PHASE_SURROGATE_NOT_REJECTED",),
        )

    prov_ok = _provenance_ok(reports, thresholds)
    det_ok = _determinism_ok(reports, thresholds)
    local_pass = _local_pass(metrics, thresholds)

    local_status = "PASS" if local_pass else "FAIL"
    artifact_status = "NOT_SUSPECTED"
    gamma_status = (
        "NO_ADMISSIBLE_CLAIM" if gamma_pass is None else ("PASS" if gamma_pass else "FAIL")
    )

    if not prov_ok:
        reasons_list.append("PROVENANCE_MISSING")
    if not det_ok:
        reasons_list.append("DETERMINISM_NOT_REPLAYED")

    if not prov_ok or not det_ok:
        # Best honest case is LOCAL_STRUCTURAL_EVIDENCE_ONLY iff
        # local_pass; otherwise NO_ADMISSIBLE_CLAIM.
        if local_pass:
            return BnSynEvidenceVerdict(
                local_structural_status=local_status,
                gamma_status=gamma_status,
                artifact_status=artifact_status,
                claim_status="LOCAL_STRUCTURAL_EVIDENCE_ONLY",
                reasons=tuple(reasons_list),
            )
        reasons_list.append("LOCAL_STRUCTURAL_FAIL")
        return BnSynEvidenceVerdict(
            local_structural_status=local_status,
            gamma_status=gamma_status,
            artifact_status=artifact_status,
            claim_status="NO_ADMISSIBLE_CLAIM",
            reasons=tuple(reasons_list),
        )

    if local_pass and gamma_pass is True:
        return BnSynEvidenceVerdict(
            local_structural_status=local_status,
            gamma_status=gamma_status,
            artifact_status=artifact_status,
            claim_status="VALIDATED_SUBSTRATE_EVIDENCE",
            reasons=(),
        )

    if local_pass:
        return BnSynEvidenceVerdict(
            local_structural_status=local_status,
            gamma_status=gamma_status,
            artifact_status=artifact_status,
            claim_status="LOCAL_STRUCTURAL_EVIDENCE_ONLY",
            reasons=tuple(reasons_list),
        )

    reasons_list.append("LOCAL_STRUCTURAL_FAIL")
    return BnSynEvidenceVerdict(
        local_structural_status=local_status,
        gamma_status=gamma_status,
        artifact_status=artifact_status,
        claim_status="NO_ADMISSIBLE_CLAIM",
        reasons=tuple(reasons_list),
    )


def build_output_document(
    bundle_dir: Path,
    metrics: BnSynStructuralMetrics,
    verdict: BnSynEvidenceVerdict,
    reports: dict[str, dict[str, Any]],
    missing_files: tuple[str, ...],
) -> dict[str, Any]:
    """Assemble the normalised JSON document written to ``--out``."""

    manifest = reports.get("run_manifest.json", {})
    robustness = reports.get("robustness_report.json", {})
    replay = robustness.get("replay_check", {}) if isinstance(robustness, dict) else {}

    return {
        "schema_version": "1.0.0",
        "source": {
            "bundle_dir": str(bundle_dir),
            "missing_files": list(missing_files),
            "required_files": list(REQUIRED_FILES),
        },
        "metrics": dataclasses.asdict(metrics),
        "verdict": dataclasses.asdict(verdict),
        "provenance": {
            "run_manifest_seed": manifest.get("seed") if isinstance(manifest, dict) else None,
            "run_manifest_cmd": manifest.get("cmd") if isinstance(manifest, dict) else None,
            "run_manifest_artifact_count": (
                len(manifest.get("artifacts", {})) if isinstance(manifest, dict) else 0
            ),
            "replay_identical": (
                bool(replay.get("identical", False)) if isinstance(replay, dict) else False
            ),
        },
        "non_claims": [
            "BN-Syn structural metrics do not by themselves prove γ ≈ 1.0.",
            "BN-Syn structural metrics do not prove cross-substrate universality.",
            "BN-Syn structural metrics do not prove emergence of any cognitive property.",
            "Surrogate-rejection here is a power-law-fit proxy, not a phase-randomized null.",
            "VALIDATED_SUBSTRATE_EVIDENCE requires a γ-side pass supplied by the caller.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import BN-Syn canonical proof bundle into NeoSynaptex structural-evidence JSON."
        ),
    )
    parser.add_argument("--bundle", required=True, type=Path, help="BN-Syn bundle directory.")
    parser.add_argument("--out", required=True, type=Path, help="Output JSON path.")
    parser.add_argument(
        "--thresholds",
        default=_DEFAULT_THRESHOLDS_PATH,
        type=Path,
        help="Thresholds YAML (default: config/bnsyn_structural_thresholds.yaml).",
    )
    args = parser.parse_args(argv)

    bundle_dir: Path = args.bundle
    out_path: Path = args.out
    thresholds_path: Path = args.thresholds

    if not bundle_dir.is_dir():
        print(f"error: --bundle {bundle_dir} is not a directory", file=sys.stderr)
        return 2

    if not thresholds_path.is_file():
        print(f"error: --thresholds {thresholds_path} is not a file", file=sys.stderr)
        return 2

    thresholds = _read_yaml(thresholds_path)
    reports, missing = load_bundle(bundle_dir)

    if missing:
        # Emit a fail-closed document so downstream consumers can still
        # parse the verdict; do NOT short-circuit silently.
        empty_metrics = BnSynStructuralMetrics(
            kappa=float("nan"),
            kappa_ci_low=None,
            kappa_ci_high=None,
            avalanche_fit_quality=float("nan"),
            avalanche_distribution_summary={},
            phase_coherence=float("nan"),
            phase_surrogate_rejected=False,
        )
        verdict = BnSynEvidenceVerdict(
            local_structural_status="MISSING",
            gamma_status="NO_ADMISSIBLE_CLAIM",
            artifact_status="MISSING",
            claim_status="NO_ADMISSIBLE_CLAIM",
            reasons=tuple(f"MISSING_FILE:{m}" for m in missing),
        )
        document = build_output_document(bundle_dir, empty_metrics, verdict, reports, missing)
    else:
        metrics = extract_metrics(reports, thresholds)
        verdict = compute_verdict(metrics, reports, thresholds)
        document = build_output_document(bundle_dir, metrics, verdict, reports, missing)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    document = strict_json_sanitize(document)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(document, fh, sort_keys=True, indent=2, allow_nan=False)
        fh.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
