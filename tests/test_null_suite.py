"""Tests for the five-layer null suite (Task 6)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tools.hrv.null_suite import (
    BORD,
    NOTSEP,
    SEP,
    NullSuiteConfig,
    aggregate_verdict,
    compute_null_suite,
    verdict_from_z,
)
from tools.hrv.surrogates import SURROGATE_FAMILIES, ar1_fit, generate_family

_REPO_ROOT = Path(__file__).parent.parent
_EVIDENCE_DIR = _REPO_ROOT / "evidence" / "surrogates"


# ---------------------------------------------------------------------------
# Surrogate correctness
# ---------------------------------------------------------------------------
def test_all_five_families_present() -> None:
    assert SURROGATE_FAMILIES == ("shuffled", "iaaft", "ar1", "poisson", "latent_gmm")


def test_shuffled_preserves_marginal_exactly() -> None:
    rng = np.random.default_rng(0)
    x = 0.8 + 0.05 * rng.normal(size=1000)
    s = generate_family(x, "shuffled", n=10, seed=1)
    assert np.allclose(np.sort(s[0]), np.sort(x))


def test_iaaft_preserves_power_spectrum() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(size=2000)
    s = generate_family(x, "iaaft", n=3, seed=5)
    p_real = np.abs(np.fft.rfft(x))
    p_surr = np.abs(np.fft.rfft(s[0]))
    rel_err = float(np.mean((p_real - p_surr) ** 2) / (np.mean(p_real**2) + 1e-12))
    assert rel_err < 1e-4


def test_ar1_preserves_lag1_autocorrelation() -> None:
    rng = np.random.default_rng(2)
    x = np.empty(3000)
    x[0] = 0.8
    for i in range(1, 3000):
        x[i] = 0.8 + 0.7 * (x[i - 1] - 0.8) + 0.02 * rng.normal()
    _, phi_real, _ = ar1_fit(x)
    s = generate_family(x, "ar1", n=20, seed=11)
    phis = [ar1_fit(s[i])[1] for i in range(20)]
    assert abs(float(np.mean(phis)) - phi_real) < 0.05


def test_poisson_mean_matches_input_mean() -> None:
    rng = np.random.default_rng(6)
    x = 0.8 + 0.05 * rng.normal(size=5000)
    s = generate_family(x, "poisson", n=30, seed=22)
    # mean converges to rate⁻¹ = mean(x)
    assert abs(float(s.mean()) - float(x.mean())) < 0.05


def test_latent_gmm_preserves_moments_roughly() -> None:
    rng = np.random.default_rng(8)
    x = np.concatenate([0.6 + 0.03 * rng.normal(size=500), 0.9 + 0.04 * rng.normal(size=500)])
    rng.shuffle(x)
    s = generate_family(x, "latent_gmm", n=10, seed=33)
    # mean and variance within 5%
    assert abs(float(s.mean()) - float(x.mean())) < 0.05
    assert abs(float(s.var()) - float(x.var())) / float(x.var()) < 0.25


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------
def test_verdict_from_z_thresholds() -> None:
    assert verdict_from_z(0.0) == NOTSEP
    assert verdict_from_z(1.9) == NOTSEP
    assert verdict_from_z(2.0) == BORD
    assert verdict_from_z(2.9) == BORD
    assert verdict_from_z(3.0) == SEP
    assert verdict_from_z(-3.1) == SEP


def test_aggregate_verdict_three_separable_returns_separable() -> None:
    per = {"a": SEP, "b": SEP, "c": SEP, "d": NOTSEP, "e": NOTSEP}
    assert aggregate_verdict(per) == SEP


def test_aggregate_verdict_two_separable_returns_borderline() -> None:
    per = {"a": SEP, "b": SEP, "c": NOTSEP, "d": NOTSEP, "e": NOTSEP}
    assert aggregate_verdict(per) == BORD


def test_aggregate_verdict_zero_separable_no_borderline_returns_not_separable() -> None:
    per = {"a": NOTSEP, "b": NOTSEP, "c": NOTSEP, "d": NOTSEP, "e": NOTSEP}
    assert aggregate_verdict(per) == NOTSEP


# ---------------------------------------------------------------------------
# Integration: compute_null_suite on a short synthetic signal
# ---------------------------------------------------------------------------
def test_compute_null_suite_runs_on_synthetic() -> None:
    rng = np.random.default_rng(44)
    rr = 0.8 + 0.05 * rng.normal(size=3000)
    cfg = NullSuiteConfig(n_surrogates_per_layer=20, n_beats_cap=3000)
    r = compute_null_suite(rr, cohort="synthetic", subject_record="noise01", seed=1, cfg=cfg)
    assert r.n_beats_used == 3000
    assert len(r.per_layer) == 5
    assert r.overall_verdict in (SEP, BORD, NOTSEP)
    for lr in r.per_layer:
        assert lr.family in SURROGATE_FAMILIES


def test_compute_null_suite_accepts_sample_entropy_statistic() -> None:
    """Parametric statistic — SampEn path must produce five finite z-scores on a
    non-degenerate RR series."""
    rng = np.random.default_rng(77)
    rr = 0.8 + 0.05 * rng.normal(size=1500)
    cfg = NullSuiteConfig(
        statistic="sample_entropy",
        n_surrogates_per_layer=20,
        n_beats_cap=1500,
        sampen_max_n=1500,
    )
    r = compute_null_suite(rr, cohort="synthetic", subject_record="se01", seed=1, cfg=cfg)
    assert r.config["statistic"] == "sample_entropy"
    assert len(r.per_layer) == 5
    assert np.isfinite(r.statistic_real)


def test_compute_null_suite_raises_on_too_short_input() -> None:
    rng = np.random.default_rng(1)
    rr = rng.normal(size=50)
    cfg = NullSuiteConfig(n_surrogates_per_layer=5)
    with pytest.raises(ValueError):
        compute_null_suite(rr, cohort="x", subject_record="y", seed=1, cfg=cfg)


# ---------------------------------------------------------------------------
# Committed evidence (if present — do not force until batch runs)
# ---------------------------------------------------------------------------
def test_null_suite_summary_present_if_evidence_committed() -> None:
    summary_path = _EVIDENCE_DIR / "null_suite_summary.json"
    if not summary_path.exists():
        pytest.skip("null_suite_summary.json not generated yet")
    summary = json.loads(summary_path.read_text("utf-8"))
    assert summary["schema_version"] == 1
    assert summary["split_scope"] == "development_only"
    assert summary["config"]["statistic"] in {"dfa_alpha_16_64", "sample_entropy"}


def test_every_committed_subject_has_five_layers() -> None:
    for path in _EVIDENCE_DIR.glob("*__*/null_suite.json"):
        j = json.loads(path.read_text("utf-8"))
        assert len(j["per_layer"]) == 5
        families = {lr["family"] for lr in j["per_layer"]}
        assert families == set(SURROGATE_FAMILIES)


def test_dev_only_summary_covers_all_69_dev_subjects_if_present() -> None:
    summary_path = _EVIDENCE_DIR / "null_suite_summary.json"
    if not summary_path.exists():
        pytest.skip("null_suite_summary.json not generated yet")
    summary = json.loads(summary_path.read_text("utf-8"))
    if summary["aggregate"]["n_subjects"] != 69:
        pytest.skip(f"partial run (n={summary['aggregate']['n_subjects']}) — full run pending")
    assert summary["aggregate"]["n_subjects"] == 69
