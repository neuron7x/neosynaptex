"""Importer tests for ``tools/import_bnsyn_structural_evidence.py``.

Numbered tests:
6. Missing required file → ``claim_status == NO_ADMISSIBLE_CLAIM`` and
   the missing filename appears in ``verdict.reasons``.
7. NaN κ in ``criticality_report.json`` → fail-closed verdict.
8. Surrogate proxy disabled (i.e. ``phase_surrogate_rejected`` stays
   False even with PASS verdict) → ``ARTIFACT_SUSPECTED``.
9. End-to-end happy path: synthetic bundle with all required files,
   PASS validity, replay identical, non-empty manifest →
   ``LOCAL_STRUCTURAL_EVIDENCE_ONLY`` (NEVER VALIDATED — that requires
   a γ-side pass which the importer does not synthesise).
10. Importer NEVER emits ``VALIDATED_SUBSTRATE_EVIDENCE`` from local
    bundle alone, even on a "perfect" bundle — confirms the κ ≠ γ
    invariant.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.import_bnsyn_structural_evidence import (  # noqa: E402
    REQUIRED_FILES,
    build_output_document,
    compute_verdict,
    extract_metrics,
    load_bundle,
    main,
    strict_json_sanitize,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_THRESHOLDS_PATH = _REPO_ROOT / "config" / "bnsyn_structural_thresholds.yaml"


def _load_thresholds() -> dict[str, Any]:
    with _THRESHOLDS_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


def _write_bundle(
    bundle_dir: Path,
    *,
    sigma_mean: float = 1.02,
    p_value: float = 0.42,
    validity_verdict: str = "PASS",
    coherence_mean: float = 0.73,
    avalanche_count: int = 250,
    replay_identical: bool = True,
    artifacts: dict[str, str] | None = None,
    omit: tuple[str, ...] = (),
) -> None:
    """Write a synthetic BN-Syn bundle into ``bundle_dir``."""

    bundle_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict[str, Any]] = {
        "criticality_report.json": {
            "schema_version": "1.0.0",
            "seed": 11,
            "N": 200,
            "dt_ms": 1.0,
            "duration_ms": 10000.0,
            "steps": 10000,
            "sigma_mean": sigma_mean,
            "sigma_final": sigma_mean,
            "sigma_variance": 0.0009,
            "rate_mean_hz": 1.5,
            "rate_peak_hz": 4.0,
            "spike_events": 12345,
            "sigma_distance_from_1": 0.02,
            "sigma_within_band_fraction": 0.99,
            "active_steps_fraction": 0.85,
            "nonzero_rate_steps_fraction": 0.85,
            "rate_cv": 0.5,
            "burstiness_proxy": 1.2,
        },
        "avalanche_report.json": {
            "schema_version": "1.0.0",
            "seed": 11,
            "N": 200,
            "dt_ms": 1.0,
            "duration_ms": 10000.0,
            "steps": 10000,
            "bin_width_steps": 1,
            "avalanche_count": avalanche_count,
            "active_bin_fraction": 0.7,
            "size_mean": 4.5,
            "size_max": 87,
            "duration_mean": 3.1,
            "duration_max": 22,
            "sizes": [],
            "durations": [],
            "nonempty_bins": 7000,
            "largest_avalanche_fraction": 0.04,
            "size_variance": 9.0,
            "duration_variance": 4.0,
        },
        "avalanche_fit_report.json": {
            "schema_version": "1.0.0",
            "alpha": 1.51,
            "tau": 2.0,
            "xmin": 1,
            "ks_distance": 0.04,
            "p_value": p_value,
            "likelihood_ratio": 1.5,
            "fit_method": "mle",
            "sample_size": avalanche_count,
            "tau_meaning": "duration_exponent",
            "validity": {
                "verdict": validity_verdict,
                "reasons": [],
                "thresholds": {
                    "min_tail_count": 30,
                    "p_value_min": 0.10,
                    "ks_max": 0.10,
                },
            },
        },
        "phase_space_report.json": {
            "schema_version": "1.1.0",
            "seed": 11,
            "N": 200,
            "dt_ms": 1.0,
            "duration_ms": 10000.0,
            "steps": 10000,
            "state_axes": ["population_rate_hz", "sigma", "coherence"],
            "point_count": 10000,
            "rate_mean_hz": 1.5,
            "sigma_mean": sigma_mean,
            "coherence_mean": coherence_mean,
            "coherence_std": 0.05,
            "coherence_min": 0.5,
            "coherence_max": 0.9,
            "rate_sigma_correlation": 0.1,
            "rate_coherence_correlation": 0.2,
            "trajectory_length_l2": 12.3,
            "bounding_box": {
                "rate_min": 0.0,
                "rate_max": 4.0,
                "sigma_min": 0.9,
                "sigma_max": 1.1,
                "coherence_min": 0.5,
                "coherence_max": 0.9,
            },
            "centroid": {"rate": 1.5, "sigma": 1.02, "coherence": coherence_mean},
            "activity_map": {
                "axes": ["population_rate_hz", "sigma"],
                "grid_size": 32,
                "occupied_cell_count": 200,
                "occupied_cell_fraction": 0.2,
                "max_cell_count": 50,
                "density_mean": 1.0,
            },
            "artifacts": {
                "plots": [
                    "phase_space_rate_sigma.png",
                    "phase_space_rate_coherence.png",
                    "phase_space_activity_map.png",
                ],
                "traces": [
                    "population_rate_trace.npy",
                    "sigma_trace.npy",
                    "coherence_trace.npy",
                ],
            },
        },
        "run_manifest.json": {
            "schema_version": "1.1.0",
            "cmd": "bnsyn run --profile canonical --plot --export-proof",
            "bundle_contract": "canonical-export-proof",
            "export_proof": True,
            "seed": 11,
            "steps": 10000,
            "N": 200,
            "dt_ms": 1.0,
            "duration_ms": 10000.0,
            "completed_stages": [
                "live_run",
                "summary_reports",
                "avalanche_and_fit",
                "robustness_envelope",
                "manifest",
                "proof_report",
                "product_surface",
            ],
            "artifacts": artifacts
            or {
                "criticality_report.json": "a" * 64,
                "avalanche_report.json": "b" * 64,
                "avalanche_fit_report.json": "c" * 64,
                "phase_space_report.json": "d" * 64,
                "robustness_report.json": "e" * 64,
            },
        },
        "robustness_report.json": {
            "schema_version": "1.0.0",
            "seed_set": [11, 23, 37, 41, 53, 67, 79, 83, 97, 101],
            "replay_check": {
                "seed": 11,
                "required_traces": [
                    "population_rate_trace.npy",
                    "sigma_trace.npy",
                    "coherence_trace.npy",
                ],
                "hashes": [],
                "identical": replay_identical,
            },
            "runs": [
                {
                    "seed": s,
                    "rate_mean_hz": 1.5,
                    "sigma_mean": 1.02,
                    "avalanche_count": 250,
                    "avalanche_exponent": 1.51,
                }
                for s in [11, 23, 37, 41, 53, 67, 79, 83, 97, 101]
            ],
        },
    }

    for name, payload in files.items():
        if name in omit:
            continue
        (bundle_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


# 6
def test_missing_file_yields_no_admissible_claim(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle, omit=("criticality_report.json",))
    out = tmp_path / "evidence.json"
    rc = main(["--bundle", str(bundle), "--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["verdict"]["claim_status"] == "NO_ADMISSIBLE_CLAIM"
    reasons = doc["verdict"]["reasons"]
    assert any("criticality_report.json" in r for r in reasons)


# 7
def test_nan_kappa_yields_fail_closed(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle, sigma_mean=float("nan"))
    out = tmp_path / "evidence.json"
    rc = main(["--bundle", str(bundle), "--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["verdict"]["claim_status"] == "NO_ADMISSIBLE_CLAIM"
    assert "KAPPA_NOT_FINITE" in doc["verdict"]["reasons"]


# 8
def test_validity_fail_yields_artifact_suspected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    # FAIL verdict on the avalanche fit blocks the surrogate proxy →
    # phase_surrogate_rejected stays False → ARTIFACT_SUSPECTED.
    _write_bundle(bundle, validity_verdict="FAIL")
    reports, missing = load_bundle(bundle)
    assert missing == ()
    metrics = extract_metrics(reports, _load_thresholds())
    assert metrics.phase_surrogate_rejected is False
    verdict = compute_verdict(metrics, reports, _load_thresholds())
    assert verdict.claim_status == "ARTIFACT_SUSPECTED"
    assert verdict.artifact_status == "ARTIFACT_SUSPECTED"


# 9
def test_happy_path_local_structural_only(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)
    out = tmp_path / "evidence.json"
    rc = main(["--bundle", str(bundle), "--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    # Best honest case from importer alone.
    assert doc["verdict"]["claim_status"] == "LOCAL_STRUCTURAL_EVIDENCE_ONLY"
    assert doc["verdict"]["local_structural_status"] == "PASS"
    assert doc["verdict"]["artifact_status"] == "NOT_SUSPECTED"
    assert doc["verdict"]["gamma_status"] == "NO_ADMISSIBLE_CLAIM"


# 10
def test_importer_never_emits_validated(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)  # perfect bundle
    reports, missing = load_bundle(bundle)
    assert missing == ()
    metrics = extract_metrics(reports, _load_thresholds())
    verdict = compute_verdict(metrics, reports, _load_thresholds())
    # Even on a perfect bundle, the importer cannot reach
    # VALIDATED_SUBSTRATE_EVIDENCE without a caller-supplied gamma_pass.
    assert verdict.claim_status != "VALIDATED_SUBSTRATE_EVIDENCE"
    # Confirm: opening the gate explicitly DOES upgrade.
    upgraded = compute_verdict(metrics, reports, _load_thresholds(), gamma_pass=True)
    assert upgraded.claim_status == "VALIDATED_SUBSTRATE_EVIDENCE"


def test_required_files_constant_is_complete() -> None:
    """Defensive: REQUIRED_FILES must include all six bundle files."""
    expected = {
        "criticality_report.json",
        "avalanche_report.json",
        "avalanche_fit_report.json",
        "phase_space_report.json",
        "run_manifest.json",
        "robustness_report.json",
    }
    assert set(REQUIRED_FILES) == expected


def test_missing_file_output_is_strict_json_without_nan_tokens(tmp_path: Path) -> None:
    """Fail-closed missing-file output must be strict-JSON: no NaN/Infinity tokens."""
    bundle = tmp_path / "bundle"
    _write_bundle(bundle, omit=("criticality_report.json",))
    out = tmp_path / "evidence.json"

    rc = main(["--bundle", str(bundle), "--out", str(out)])

    assert rc == 0
    raw = out.read_text(encoding="utf-8")
    # Strict JSON (RFC 8259) forbids these tokens. Their presence would
    # mean json.dump silently emitted the Python float("nan") sentinels.
    assert "NaN" not in raw
    assert "Infinity" not in raw
    assert "-Infinity" not in raw

    doc = json.loads(raw)
    assert doc["verdict"]["claim_status"] == "NO_ADMISSIBLE_CLAIM"
    assert doc["metrics"]["kappa"] is None
    assert doc["metrics"]["avalanche_fit_quality"] is None
    assert doc["metrics"]["phase_coherence"] is None


def test_strict_json_sanitizer_converts_nonfinite_nested_values() -> None:
    """Sanitizer maps NaN/inf to None recursively across dicts, lists, tuples."""
    payload = {
        "kappa": float("nan"),
        "ci": [float("inf"), float("-inf"), 1.0],
        "summary": {"mean": float("nan"), "count": 7},
        "tuple_field": (float("nan"), 0.5),
        "ok_int": 3,
        "ok_str": "x",
        "ok_bool": True,
    }
    out = strict_json_sanitize(payload)
    assert out["kappa"] is None
    assert out["ci"] == [None, None, 1.0]
    assert out["summary"]["mean"] is None
    assert out["summary"]["count"] == 7
    assert out["tuple_field"] == [None, 0.5]
    assert out["ok_int"] == 3
    assert out["ok_str"] == "x"
    assert out["ok_bool"] is True
    # And the result round-trips through strict JSON.
    raw = json.dumps(out, allow_nan=False, sort_keys=True)
    assert "NaN" not in raw
    assert "Infinity" not in raw


def test_build_output_document_shape(tmp_path: Path) -> None:
    """Output document carries the documented top-level keys."""
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)
    reports, missing = load_bundle(bundle)
    metrics = extract_metrics(reports, _load_thresholds())
    verdict = compute_verdict(metrics, reports, _load_thresholds())
    doc = build_output_document(bundle, metrics, verdict, reports, missing)
    assert set(doc.keys()) >= {
        "schema_version",
        "source",
        "metrics",
        "verdict",
        "provenance",
        "non_claims",
    }
    # non_claims must remain non-empty — it's the contract surface that
    # tells callers what BN-Syn does NOT prove.
    assert len(doc["non_claims"]) >= 5
