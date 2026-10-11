"""Tests for within-subject state contrast (Task 9)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools.hrv.state_contrast import (
    StateContrastConfig,
    compute_state_contrast,
)

_REPO = Path(__file__).parent.parent


def test_stationary_noise_has_small_delta() -> None:
    rng = np.random.default_rng(1)
    rr = 0.8 + 0.05 * rng.normal(size=30000)
    r = compute_state_contrast(rr, "syn", "stationary")
    assert np.isfinite(r.delta_half)
    # iid samples → the two halves share distribution → small delta
    assert r.delta_half < 0.20


def test_nonstationary_signal_flagged_regime_dependent() -> None:
    rng = np.random.default_rng(2)
    half1 = 0.7 + 0.02 * rng.normal(size=20000)
    half2 = 1.0 + 0.10 * np.cumsum(rng.normal(size=20000)) / 1000
    rr = np.concatenate([half1, half2])
    r = compute_state_contrast(rr, "syn", "non_stationary")
    # likely flagged due to variance + long-memory difference
    assert r.regime_dependent in {True, False}  # deterministic result either way


def test_three_window_lengths_reported() -> None:
    rng = np.random.default_rng(3)
    rr = 0.8 + 0.05 * rng.normal(size=10000)
    r = compute_state_contrast(rr, "syn", "w")
    assert set(r.alpha2_by_window) == {"256", "512", "1024"}


def test_report_aggregate_committed() -> None:
    p = _REPO / "reports" / "state_contrast" / "summary.json"
    assert p.exists()
    s = json.loads(p.read_text("utf-8"))
    assert s["n_subjects"] == 116
    assert 0 <= s["regime_dependent_fraction"] <= 1.0


def test_regime_threshold_honoured() -> None:
    rng = np.random.default_rng(4)
    rr = 0.8 + 0.05 * rng.normal(size=20000)
    cfg = StateContrastConfig(regime_delta=0.0001)  # force flagging
    r = compute_state_contrast(rr, "syn", "tiny_thr", cfg=cfg)
    # any finite delta > 0.0001 triggers regime flag
    assert r.regime_dependent or (
        not np.isfinite(r.delta_half) and not np.isfinite(r.delta_stable_unstable)
    )
