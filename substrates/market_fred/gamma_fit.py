"""γ-estimation on FRED macro time series via Welch PSD + Theil-Sen.

Canonical method per ``docs/MEASUREMENT_METHOD_HIERARCHY.md``:

* Primary method for this substrate class is **specparam/IRASA**,
  but for the initial bootstrapping replication we use the simpler
  Welch-PSD + Theil-Sen log-log regression as a **bounded secondary
  method**. This is explicitly labelled as such in every result
  record. A specparam upgrade is a follow-up PR once the substrate
  has at least one prereg filed.
* Null families used in the initial pass: shuffled + AR(1) +
  IAAFT. OU/latent-variable surrogate are Phase VI §Step 24
  follow-ups. Poisson is not applicable — this is a continuous
  time series.

Design invariants
-----------------

* Deterministic under fixed seed (bootstrap, surrogate generation).
* Null comparison via |z|≥3 threshold per NULL_MODEL_HIERARCHY.md §4.
* Every result records the exact method label so an upgrade to
  specparam later leaves a clean audit trail.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
from scipy import signal
from scipy.stats import theilslopes

__all__ = [
    "GammaFit",
    "NullComparison",
    "fit_gamma_log_log_psd",
    "generate_shuffled_surrogate",
    "generate_ar1_surrogate",
    "generate_iaaft_surrogate",
    "null_comparison",
]


@dataclasses.dataclass(frozen=True)
class GammaFit:
    """Result of one γ-estimation on a time series."""

    gamma: float
    ci_low: float
    ci_high: float
    r2: float
    n_points: int
    method_label: str
    fit_freq_lo: float
    fit_freq_hi: float
    n_frequencies_fit: int


@dataclasses.dataclass(frozen=True)
class NullComparison:
    """z-score of γ_real against a null family distribution."""

    null_family: str
    n_surrogates: int
    mu: float
    sigma: float
    z_score: float
    null_ci_low: float
    null_ci_high: float
    real_outside_null_ci: bool
    separable_at_z3: bool


def _welch_psd(
    x: np.ndarray, fs: float = 1.0, nperseg: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Return (frequencies, PSD) from Welch's method."""

    if nperseg is None:
        nperseg = min(256, len(x))
    f, p = signal.welch(x, fs=fs, nperseg=nperseg, detrend="constant")
    return f, p


def fit_gamma_log_log_psd(
    x: np.ndarray,
    *,
    fs: float = 1.0,
    f_lo: float | None = None,
    f_hi: float | None = None,
    bootstrap_n: int = 500,
    seed: int = 42,
    method_label: str = "welch_psd_theilsen",
) -> GammaFit:
    """Fit the aperiodic slope of a time series via log-log PSD.

    Uses Welch's method for the PSD estimate and Theil-Sen robust
    regression on log(f)-log(PSD). Bootstrap CI is computed by
    resampling the frequency-PSD pairs.

    The γ returned is the POSITIVE slope magnitude: for a
    1/f^γ spectrum, log(PSD) ≈ -γ·log(f) + c, so Theil-Sen slope
    is -γ; we return ``γ = -slope``.

    Parameters
    ----------
    x:
        1-D time series. NaNs are dropped before fitting.
    fs:
        Sampling frequency. For monthly data fs=1.0 (cycles/month);
        adjust if aggregating differently.
    f_lo, f_hi:
        Optional frequency band to restrict the fit. If None, uses
        f > 0 to avoid log(0).
    bootstrap_n:
        Number of bootstrap resamples for CI95.
    seed:
        RNG seed for bootstrap determinism.

    Returns
    -------
    GammaFit with γ, CI95, r², n_frequencies_fit, and the exact
    method label.
    """

    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 16:
        raise ValueError(f"too few samples for Welch PSD: n={len(x)}")

    f, p = _welch_psd(x, fs=fs)
    mask = f > 0
    if f_lo is not None:
        mask &= f >= f_lo
    if f_hi is not None:
        mask &= f <= f_hi
    f_fit = f[mask]
    p_fit = p[mask]
    p_fit = np.clip(p_fit, 1e-30, None)  # avoid log(0)

    log_f = np.log(f_fit)
    log_p = np.log(p_fit)

    slope, intercept, lo, hi = theilslopes(log_p, log_f)
    gamma = float(-slope)
    gamma_ci_lo = float(-hi)
    gamma_ci_hi = float(-lo)

    yhat = slope * log_f + intercept
    ss_r = float(np.sum((log_p - yhat) ** 2))
    ss_t = float(np.sum((log_p - log_p.mean()) ** 2))
    r2 = 1.0 - ss_r / ss_t if ss_t > 1e-12 else 0.0

    # Bootstrap CI (resample frequency-PSD pairs)
    if bootstrap_n > 0:
        rng = np.random.default_rng(seed)
        boot_gammas: list[float] = []
        n = len(log_f)
        for _ in range(bootstrap_n):
            idx = rng.integers(0, n, size=n)
            coeffs = np.polyfit(log_f[idx], log_p[idx], 1)
            boot_gammas.append(float(-coeffs[0]))
        boot_sorted = sorted(boot_gammas)
        ci_low_b = boot_sorted[int(0.025 * len(boot_sorted))]
        ci_high_b = boot_sorted[int(0.975 * len(boot_sorted))]
        # Take the wider of Theil-Sen CI and bootstrap CI — conservative.
        final_ci_low = min(gamma_ci_lo, ci_low_b)
        final_ci_high = max(gamma_ci_hi, ci_high_b)
    else:
        final_ci_low = gamma_ci_lo
        final_ci_high = gamma_ci_hi

    return GammaFit(
        gamma=round(gamma, 4),
        ci_low=round(final_ci_low, 4),
        ci_high=round(final_ci_high, 4),
        r2=round(float(r2), 4),
        n_points=int(len(x)),
        method_label=method_label,
        fit_freq_lo=float(f_fit[0]),
        fit_freq_hi=float(f_fit[-1]),
        n_frequencies_fit=int(len(f_fit)),
    )


# ---------------------------------------------------------------------------
# Null-family surrogates
# ---------------------------------------------------------------------------


def generate_shuffled_surrogate(x: np.ndarray, seed: int) -> np.ndarray:
    """Destroy temporal structure; preserve marginal distribution."""

    rng = np.random.default_rng(seed)
    return rng.permutation(x)


def generate_ar1_surrogate(x: np.ndarray, seed: int) -> np.ndarray:
    """AR(1) mean-reverting linear diffusion, matched τ and σ."""

    # Estimate AR(1) params from empirical x.
    x_centred = x - np.mean(x)
    if len(x_centred) < 2:
        raise ValueError("series too short for AR(1) fit")
    num = float(np.dot(x_centred[:-1], x_centred[1:]))
    den = float(np.dot(x_centred[:-1], x_centred[:-1]))
    phi = num / den if den > 0 else 0.0
    phi = max(min(phi, 0.99), -0.99)
    resid = x_centred[1:] - phi * x_centred[:-1]
    sigma = float(np.std(resid))
    rng = np.random.default_rng(seed)
    y = np.zeros(len(x))
    y[0] = rng.normal(0, sigma / math.sqrt(max(1 - phi * phi, 1e-6)))
    for i in range(1, len(y)):
        y[i] = phi * y[i - 1] + rng.normal(0, sigma)
    return y + float(np.mean(x))


def generate_iaaft_surrogate(x: np.ndarray, seed: int, n_iter: int = 100) -> np.ndarray:
    """IAAFT surrogate: preserves power spectrum + marginal distribution."""

    rng = np.random.default_rng(seed)
    x_sorted = np.sort(x)
    x_fft = np.fft.rfft(x)
    x_mag = np.abs(x_fft)
    # Start with random permutation
    y = rng.permutation(x)
    for _ in range(n_iter):
        y_fft = np.fft.rfft(y)
        # Impose original amplitude spectrum
        y_phase = np.angle(y_fft)
        y_fft_new = x_mag * np.exp(1j * y_phase)
        y_spec = np.fft.irfft(y_fft_new, n=len(x))
        # Impose original marginal distribution by rank-matching
        ranks = np.argsort(np.argsort(y_spec))
        y = x_sorted[ranks]
    return y


def null_comparison(
    real_gamma: float,
    x: np.ndarray,
    null_family: str,
    *,
    n_surrogates: int = 500,
    seed: int = 42,
    **fit_kwargs: Any,
) -> NullComparison:
    """Compare real γ against a null-family surrogate distribution.

    Returns a NullComparison record with z-score and separability
    verdict per NULL_MODEL_HIERARCHY.md §4.
    """

    generators = {
        "shuffled": generate_shuffled_surrogate,
        "ar1": generate_ar1_surrogate,
        "iaaft": generate_iaaft_surrogate,
    }
    gen = generators.get(null_family)
    if gen is None:
        raise ValueError(f"unknown null family: {null_family}; supported: {sorted(generators)}")

    rng_seed_base = seed
    surrogate_gammas: list[float] = []
    for i in range(n_surrogates):
        surr = gen(x, rng_seed_base + i)
        try:
            fit = fit_gamma_log_log_psd(surr, seed=rng_seed_base + i, bootstrap_n=0, **fit_kwargs)
            surrogate_gammas.append(fit.gamma)
        except (ValueError, np.linalg.LinAlgError):
            continue

    if len(surrogate_gammas) < max(10, n_surrogates // 10):
        raise RuntimeError(f"too few valid surrogates ({len(surrogate_gammas)}/{n_surrogates})")

    arr = np.asarray(surrogate_gammas)
    mu = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    z = (real_gamma - mu) / sigma if sigma > 1e-10 else 0.0
    ci_lo = float(np.percentile(arr, 2.5))
    ci_hi = float(np.percentile(arr, 97.5))
    real_outside = not (ci_lo <= real_gamma <= ci_hi)
    separable = abs(z) >= 3.0 and real_outside

    return NullComparison(
        null_family=null_family,
        n_surrogates=len(surrogate_gammas),
        mu=round(mu, 4),
        sigma=round(sigma, 4),
        z_score=round(z, 3),
        null_ci_low=round(ci_lo, 4),
        null_ci_high=round(ci_hi, 4),
        real_outside_null_ci=real_outside,
        separable_at_z3=separable,
    )
