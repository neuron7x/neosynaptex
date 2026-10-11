"""Tests for the blind external-validation pipeline (Task 8)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tools.data.analysis_split import SplitLeakError, enforce_dev_only, load_split
from tools.hrv.blind_validation import (
    THRESHOLDS_FROZEN_PATH,
    FrozenThresholds,
    MetricThreshold,
    auc_mann_whitney,
    cohens_d,
    load_baseline_panels,
    load_frozen_thresholds,
    score_external,
    validation_report,
)

_REPO_ROOT = Path(__file__).parent.parent
_BASELINE_DIR = _REPO_ROOT / "results" / "hrv_baseline"
_REPORT_PATH = _REPO_ROOT / "reports" / "blind_validation" / "report.json"


# ---------------------------------------------------------------------------
# Primitive math
# ---------------------------------------------------------------------------
def test_auc_mann_whitney_perfect_separation() -> None:
    auc = auc_mann_whitney([2.0, 3.0, 4.0], [-1.0, 0.0, 1.0])
    assert auc == 1.0


def test_auc_mann_whitney_identical_distributions_near_half() -> None:
    rng = np.random.default_rng(42)
    a = rng.normal(size=500)
    b = rng.normal(size=500)
    auc = auc_mann_whitney(a, b)
    assert 0.4 < auc < 0.6


def test_cohens_d_large_separation() -> None:
    rng = np.random.default_rng(1)
    a = rng.normal(loc=2.0, scale=1.0, size=500)
    b = rng.normal(loc=0.0, scale=1.0, size=500)
    d = cohens_d(a, b)
    assert 1.8 < d < 2.2


def test_cohens_d_nan_on_empty() -> None:
    assert np.isnan(cohens_d([1.0], [0.0]))


# ---------------------------------------------------------------------------
# Threshold storage round-trip
# ---------------------------------------------------------------------------
def test_metric_threshold_predict_directions() -> None:
    hi = MetricThreshold(metric="x", threshold=5.0, direction="healthy_high")
    assert hi.predict(10.0) == 0
    assert hi.predict(2.0) == 1
    lo = MetricThreshold(metric="y", threshold=5.0, direction="healthy_low")
    assert lo.predict(10.0) == 1
    assert lo.predict(2.0) == 0
    # NaN → -1 (abstain)
    assert hi.predict(float("nan")) == -1


def test_frozen_thresholds_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "thr.yaml"
    frozen = FrozenThresholds(
        thresholds={
            "sdnn_ms": MetricThreshold("sdnn_ms", 100.5, "healthy_high"),
            "dfa_alpha2": MetricThreshold("dfa_alpha2", 1.05, "healthy_low"),
        },
        split_sha256="abc",
        frozen_utc="2026-04-14T00:00:00Z",
    )
    frozen.dump_yaml(path)
    read = load_frozen_thresholds(path)
    assert set(read) == {"sdnn_ms", "dfa_alpha2"}
    assert read["sdnn_ms"].threshold == pytest.approx(100.5)
    assert read["sdnn_ms"].direction == "healthy_high"
    assert read["dfa_alpha2"].direction == "healthy_low"


# ---------------------------------------------------------------------------
# Calibration happens on DEV only — gate check
# ---------------------------------------------------------------------------
def test_calibration_reads_dev_panel_under_dev_gate() -> None:
    """Loading dev subjects under enforce_dev_only must NOT raise."""
    split = load_split()
    with enforce_dev_only():
        panels = load_baseline_panels(split.development.subjects, results_dir=_BASELINE_DIR)
    assert len(panels["_label"]) == split.development.n_subjects


def test_loading_external_under_dev_gate_raises() -> None:
    """Loading external subjects under enforce_dev_only must raise — the
    baseline loader does not itself assert, so this check is *currently*
    on the orchestrator level; if the whole validation_report wraps reads
    properly we rely on enforce_dev_only as the outer gate. This test
    just confirms assert_not_external behaves on external refs."""
    from tools.data.analysis_split import assert_not_external

    split = load_split()
    ext_refs = split.external.subjects[:1]
    with enforce_dev_only(), pytest.raises(SplitLeakError):
        assert_not_external(ext_refs)


# ---------------------------------------------------------------------------
# End-to-end: validation_report produces a deterministic YAML
# ---------------------------------------------------------------------------
def test_validation_report_produces_11_metrics(tmp_path: Path) -> None:
    split = load_split()
    thr_path = tmp_path / "thresholds_frozen.yaml"
    report = validation_report(
        split,
        baseline_dir=_BASELINE_DIR,
        thresholds_path=thr_path,
    )
    assert set(report["per_metric"]) == {
        "sdnn_ms",
        "rmssd_ms",
        "total_power_ms2",
        "lf_power_ms2",
        "hf_power_ms2",
        "lf_hf_ratio",
        "dfa_alpha1",
        "dfa_alpha2",
        "poincare_sd1_ms",
        "poincare_sd2_ms",
        "sample_entropy",
    }
    for key, blk in report["per_metric"].items():
        dev = blk["development"]
        ext = blk["external"]
        # both sides present
        for side in (dev, ext):
            for k in ("auc", "cohens_d", "sensitivity", "specificity"):
                assert k in side
            # auc is the normalised ≥ 0.5 form
            assert 0.5 <= side["auc"] <= 1.0 or np.isnan(side["auc"])


def test_external_score_uses_frozen_thresholds_not_refit(tmp_path: Path) -> None:
    """Re-scoring with the same frozen YAML must reproduce the external metrics
    exactly — this is the 'zero refit' invariant at the heart of audit E-02."""
    split = load_split()
    thr_path = tmp_path / "thr.yaml"
    r1 = validation_report(split, baseline_dir=_BASELINE_DIR, thresholds_path=thr_path)

    # Re-score using the SAME frozen YAML, without re-running calibration:
    ext_panels = load_baseline_panels(split.external.subjects, results_dir=_BASELINE_DIR)
    thresholds_reloaded = load_frozen_thresholds(thr_path)
    r2 = score_external(ext_panels, thresholds_reloaded)

    for key in r1["per_metric"]:
        assert r1["per_metric"][key]["external"]["sensitivity"] == pytest.approx(
            r2[key]["sensitivity"]
        )
        assert r1["per_metric"][key]["external"]["specificity"] == pytest.approx(
            r2[key]["specificity"]
        )
        assert r1["per_metric"][key]["external"]["threshold_applied"] == pytest.approx(
            r2[key]["threshold_applied"]
        )


# ---------------------------------------------------------------------------
# Committed artefacts
# ---------------------------------------------------------------------------
def test_frozen_thresholds_committed() -> None:
    assert THRESHOLDS_FROZEN_PATH.exists(), (
        "config/thresholds_frozen.yaml must be committed so reviewers can "
        "inspect the calibrated thresholds"
    )
    parsed = load_frozen_thresholds(THRESHOLDS_FROZEN_PATH)
    assert len(parsed) == 11
    for t in parsed.values():
        assert t.direction in ("healthy_high", "healthy_low")


def test_committed_report_matches_frozen_thresholds() -> None:
    assert _REPORT_PATH.exists(), "reports/blind_validation/report.json must be committed"
    report = json.loads(_REPORT_PATH.read_text("utf-8"))
    assert report["n_dev_subjects"] == 69
    assert report["n_external_subjects"] == 47
    # thresholds sha matches what the committed YAML hashes to
    import hashlib

    yaml_bytes = THRESHOLDS_FROZEN_PATH.read_bytes()
    assert hashlib.sha256(yaml_bytes).hexdigest() == report["thresholds_yaml_sha256"]
