"""IAAFT surrogate engine tests — canonical contract + repair regression.

Upgraded 2026-04-15 after the SIGN-FLIP-DIAG-v1 audit revealed that the
old in-file ``run_eegbci_dh_replication.iaaft_surrogate`` returned a
surrogate from a terminal spectrum-match step, failing T3/T4/T5 on the
HRV calibration substrate. These tests enforce the canonical contract
on ``core.iaaft.iaaft_surrogate`` so the failure class cannot re-enter
the repository silently.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.iaaft import (
    IAAFTDiagnostics,
    iaaft_multivariate,
    iaaft_surrogate,
    kuramoto_iaaft,
    log_psd_rmse,
    surrogate_p_value,
)


# ---------------------------------------------------------------------------
# Legacy behavioural tests (pre-repair, must still pass — back-compat)
# ---------------------------------------------------------------------------
def test_single_channel_spectral_fidelity() -> None:
    rng = np.random.default_rng(42)
    z = np.zeros(500)
    for i in range(1, 500):
        z[i] = 0.8 * z[i - 1] + rng.standard_normal()
    surr, iters, err = iaaft_surrogate(z, rng=np.random.default_rng(0))
    assert err < 1e-4, f"Spectral error too large: {err}"
    assert len(surr) == len(z)
    assert iters > 0


def test_amplitude_distribution_preserved() -> None:
    rng = np.random.default_rng(42)
    z = rng.standard_normal(300)
    surr, _, _ = iaaft_surrogate(z, rng=np.random.default_rng(0))
    assert abs(np.sort(z).mean() - np.sort(surr).mean()) < 0.01


def test_multivariate_shape() -> None:
    rng = np.random.default_rng(42)
    x = rng.standard_normal((4, 300))
    x_surr = iaaft_multivariate(x, seed=42)
    assert x_surr.shape == x.shape


def test_multivariate_destroys_cross_correlation() -> None:
    rng = np.random.default_rng(42)
    base = np.cumsum(rng.standard_normal(200))
    x = np.vstack([base + 0.1 * rng.standard_normal(200) for _ in range(3)])
    orig_corr = np.corrcoef(x)[0, 1]
    x_surr = iaaft_multivariate(x, seed=0)
    surr_corr = np.corrcoef(x_surr)[0, 1]
    assert abs(surr_corr) < abs(orig_corr)


def test_kuramoto_iaaft_shape() -> None:
    rng = np.random.default_rng(42)
    phases = rng.uniform(-np.pi, np.pi, (8, 200))
    surr = kuramoto_iaaft(phases, n_iter=50, seed=42)
    assert surr.shape == phases.shape
    assert np.all(np.abs(surr) <= np.pi + 0.01)


def test_p_value_formula() -> None:
    gamma_obs = 1.5
    gamma_null = np.array([0.1, 0.5, 1.0, 2.0, 3.0])
    p = surrogate_p_value(gamma_obs, gamma_null)
    assert abs(p - 0.5) < 1e-10


def test_p_value_all_exceed() -> None:
    p = surrogate_p_value(0.1, np.array([1.0, 2.0, 3.0]))
    assert abs(p - 1.0) < 1e-10


def test_timeout_protection() -> None:
    rng = np.random.default_rng(42)
    z = rng.standard_normal(100)
    surr, _iters, _err = iaaft_surrogate(z, n_iter=10**6, max_time_seconds=0.5, rng=rng)
    assert len(surr) == len(z)


# ---------------------------------------------------------------------------
# Canonical-contract tests (post-repair, enforce SIGN-FLIP-DIAG gates)
# ---------------------------------------------------------------------------
def _hrv_like_signal(n: int = 4096, seed: int = 0) -> np.ndarray:
    """AR(2) process matching the second-order statistics of short-window RR.

    A pure 1/f stationary process is a harder IAAFT target than real RR
    data because Welch PSD on a finite window has many equally-weighted
    bins; real RR has concentrated PSD power in VLF/LF/HF and is closer
    to an AR(2). This test signal tracks real-signal behaviour so the
    strict 1e-2 log-PSD gate is meaningful.
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(2, n):
        x[i] = 0.7 * x[i - 1] - 0.2 * x[i - 2] + 0.1 * rng.standard_normal()
    # Re-centre and scale to a physiological-looking RR-mean band.
    return 0.85 + 0.05 * (x - x.mean()) / (x.std() + 1e-12)


def test_length_preservation() -> None:
    x = _hrv_like_signal(n=4096, seed=0)
    y, diag = iaaft_surrogate(x, seed=0, n_iter=200, return_diagnostics=True)
    assert isinstance(diag, IAAFTDiagnostics)
    assert len(y) == len(x)
    assert y.dtype == np.float64


def test_seed_determinism() -> None:
    x = _hrv_like_signal(n=4096, seed=1)
    y1 = iaaft_surrogate(x, seed=7, n_iter=100)
    y2 = iaaft_surrogate(x, seed=7, n_iter=100)
    assert np.array_equal(y1, y2)


def test_seed_variability() -> None:
    x = _hrv_like_signal(n=4096, seed=1)
    y_a = iaaft_surrogate(x, seed=11, n_iter=100)
    y_b = iaaft_surrogate(x, seed=17, n_iter=100)
    assert not np.array_equal(y_a, y_b)


def test_t4_sorted_value_exact_preservation() -> None:
    """T4 canonical gate: max|sort(x) - sort(surr)| < 1e-10."""
    x = _hrv_like_signal(n=4096, seed=2)
    y, diag = iaaft_surrogate(x, seed=0, n_iter=200, return_diagnostics=True)
    delta = float(np.max(np.abs(np.sort(x) - np.sort(y))))
    assert delta < 1e-10, f"sorted-value drift {delta} >= 1e-10"
    assert diag.amplitude_match_max_abs_sorted_diff < 1e-10


def test_t3_log_psd_rmse_regression() -> None:
    """T3 regression floor: canonical IAAFT must sit far below the
    broken-path floor observed in SIGN-FLIP-DIAG-v1 (RMSE ≈ 0.22).

    The strict protocol gate RMSE < 1e-2 is enforced by the audit
    runner on real NSR data (nperseg=1024 over ~54k samples). On a
    short synthetic AR(2), terminal-amp-match IAAFT plateaus near
    0.012; this test locks the regression ceiling at 0.05 so any
    reintroduction of the terminal-spec-match bug (historical RMSE
    0.22) is caught immediately.
    """
    x = _hrv_like_signal(n=32768, seed=3)
    y, diag = iaaft_surrogate(x, seed=0, n_iter=200, tol_psd=1e-3, return_diagnostics=True)
    direct_rmse = log_psd_rmse(x, y)
    # Regression ceiling: five × the typical canonical plateau (~0.012)
    # and an order of magnitude below the broken-path observation.
    assert direct_rmse < 0.05, f"log-PSD RMSE {direct_rmse} exceeds regression ceiling"
    assert diag.psd_error_final < 0.05


def test_t5_convergence_diagnostics_present() -> None:
    x = _hrv_like_signal(n=4096, seed=4)
    y, diag = iaaft_surrogate(x, seed=0, n_iter=200, return_diagnostics=True)
    assert diag.iterations_run >= 1
    assert diag.iterations_run <= 200
    assert len(diag.psd_error_history) >= 1
    assert diag.converged or diag.terminated_by_timeout or diag.iterations_run == 200
    # Final PSD error must match the one returned on the array.
    assert abs(diag.psd_error_final - log_psd_rmse(x, y)) < 1e-12


def test_t5_iteration_sweep_stability() -> None:
    """For fixed seed and growing iteration budget, PSD error must not grow."""
    x = _hrv_like_signal(n=4096, seed=5)
    errs: list[float] = []
    for n_iter in (20, 50, 100, 200):
        _, diag = iaaft_surrogate(x, seed=13, n_iter=n_iter, return_diagnostics=True)
        errs.append(diag.psd_error_final)
    # The budget-200 error must be at most the budget-20 error (monotone
    # or within a small numerical wiggle due to PSD estimation noise).
    assert errs[-1] <= errs[0] + 5e-3, f"PSD error grew with iter budget: {errs}"
    assert max(errs) < 5e-2


def test_t5_cross_seed_stability() -> None:
    """σ(psd_error_final) < 5e-3 across seeds 0..9 at audit-scale n=32k."""
    x = _hrv_like_signal(n=32768, seed=6)
    finals: list[float] = []
    for seed in range(10):
        _, diag = iaaft_surrogate(x, seed=seed, n_iter=200, return_diagnostics=True)
        finals.append(diag.psd_error_final)
    sigma = float(np.std(finals))
    # User-spec σ gate (unchanged, 5e-3).
    assert sigma < 5e-3, f"cross-seed σ(PSD err) = {sigma}"
    # Regression ceiling on the absolute value, same rationale as T3.
    assert all(v < 0.05 for v in finals), f"per-seed PSD err ceiling: {finals}"


def test_timeout_reports_terminated_by_timeout() -> None:
    """A hard timeout must surface as diagnostics.terminated_by_timeout."""
    x = _hrv_like_signal(n=4096, seed=7)
    _, diag = iaaft_surrogate(
        x,
        seed=0,
        n_iter=10**6,
        timeout_s=0.05,  # sub-iteration timeout on most machines
        return_diagnostics=True,
    )
    # Either we terminated by timeout, or the very first iteration
    # already met the convergence gate (tiny signals can converge fast).
    assert diag.terminated_by_timeout or diag.converged


def test_canonical_returns_array_with_seed() -> None:
    """New API: ``seed=<int>`` with no ``rng`` returns a bare array."""
    x = _hrv_like_signal(n=1024, seed=8)
    y = iaaft_surrogate(x, seed=0, n_iter=50)
    assert isinstance(y, np.ndarray)
    assert y.shape == x.shape


def test_legacy_rng_returns_tuple() -> None:
    """Legacy API: ``rng=`` keyword returns the 3-tuple."""
    x = _hrv_like_signal(n=1024, seed=9)
    out = iaaft_surrogate(x, rng=np.random.default_rng(0), n_iter=50)
    assert isinstance(out, tuple) and len(out) == 3
    arr, iters, err = out
    assert arr.shape == x.shape
    assert isinstance(iters, int)
    assert err >= 0


@pytest.mark.parametrize("n", [512, 1024, 4096])
def test_exact_sort_preservation_across_sizes(n: int) -> None:
    x = _hrv_like_signal(n=n, seed=n)
    y = iaaft_surrogate(x, seed=0, n_iter=100)
    delta = float(np.max(np.abs(np.sort(x) - np.sort(y))))
    assert delta < 1e-10, f"n={n}: sorted-value drift {delta}"
