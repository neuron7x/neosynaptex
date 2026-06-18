"""NFI canonical contract gamma_PSD = 2H + 1 (GAP-C-01).

The audit's most consequential omission: the Plan never validates GeoSync's
primary NFI observable, the spectral exponent ``gamma`` of the order-parameter
time series, against the canonical relation ``gamma = 2H + 1`` (H = Hurst).

This module implements that contract as a *round-trip falsifiable test*:

    choose H  ->  beta := 2H + 1  ->  synthesize a 1/f^beta signal
              ->  measure beta_hat from its PSD  ->  H_hat := (beta_hat - 1)/2
              ->  require |H_hat - H| < tol .

A correct estimator recovers H; a broken one (or a non-fractal input such as
white noise) fails. The relation gamma = 2H + 1 is the fractional-Brownian-motion
spectral identity (Mandelbrot & Van Ness 1968; Flandrin 1989).

References
----------
* Mandelbrot, B. & Van Ness, J. (1968). Fractional Brownian motions. SIAM Rev.
* Flandrin, P. (1989). On the spectrum of fractional Brownian motions. IEEE TIT.
* Welch, P. (1967). The use of FFT for the estimation of power spectra. IEEE.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import signal

Array = NDArray[np.float64]


def gamma_from_hurst(h: float) -> float:
    """Canonical NFI relation: gamma = 2H + 1."""
    return 2.0 * h + 1.0


def hurst_from_gamma(gamma: float) -> float:
    """Inverse canonical relation: H = (gamma - 1) / 2."""
    return (gamma - 1.0) / 2.0


def synth_power_law(n: int, beta: float, *, seed: int = 0) -> Array:
    """Synthesize a real signal whose PSD ~ f^{-beta} (fBm-class for beta=2H+1).

    White noise is shaped in the frequency domain by 1/f^{beta/2}. The DC bin is
    zeroed (no infinite power at f=0). Deterministic for a given seed.
    """
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0)
    filt = np.ones_like(freqs)
    nz = freqs > 0
    filt[nz] = freqs[nz] ** (-beta / 2.0)
    filt[~nz] = 0.0
    shaped = np.fft.irfft(spectrum * filt, n=n)
    return np.asarray(shaped, dtype=np.float64)


@dataclass(frozen=True)
class SpectralFit:
    """Result of a log-log PSD slope fit."""

    beta: float
    r_squared: float
    n_points: int


def psd_slope(
    x: Array, *, fs: float = 1.0, fmin_frac: float = 0.02, fmax_frac: float = 0.4
) -> SpectralFit:
    """Estimate the positive spectral exponent beta from a Welch PSD log-log fit.

    Fits ``log P(f) = c - beta log f`` over an interior band (avoids DC leakage
    and the high-frequency noise floor). Returns beta (>0 for reddened signals)
    and the fit R^2.
    """
    x = np.asarray(x, dtype=np.float64)
    nper = min(len(x), max(256, len(x) // 8))
    f, pxx = signal.welch(x, fs=fs, nperseg=nper, detrend="constant")
    band = (f > fmax_frac * 0.0 + fs * fmin_frac) & (f < fs * fmax_frac) & (pxx > 0)
    if band.sum() < 5:
        raise ValueError("insufficient spectral support for slope fit")
    lf = np.log(f[band])
    lp = np.log(pxx[band])
    slope, intercept = np.polyfit(lf, lp, 1)
    pred = slope * lf + intercept
    ss_res = np.sum((lp - pred) ** 2)
    ss_tot = np.sum((lp - lp.mean()) ** 2)
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return SpectralFit(beta=float(-slope), r_squared=r2, n_points=int(band.sum()))


@dataclass(frozen=True)
class CanonicalVerdict:
    """Verdict for the gamma = 2H + 1 contract."""

    h_true: float
    gamma_expected: float
    gamma_measured: float
    h_recovered: float
    abs_error_h: float
    passed: bool


def verify_gamma_2h1(
    h_true: float,
    *,
    n: int = 1 << 14,
    n_avg: int = 16,
    tol: float = 0.12,
    seed: int = 0,
) -> CanonicalVerdict:
    """Round-trip falsifiable check of gamma = 2H + 1.

    Averages the measured exponent over ``n_avg`` independent synthetic fBm
    realizations (reduces estimator variance) and recovers H. Passes iff the
    recovered H is within ``tol`` of the requested H.
    """
    gamma_expected = gamma_from_hurst(h_true)
    betas = [
        psd_slope(synth_power_law(n, gamma_expected, seed=seed + k)).beta for k in range(n_avg)
    ]
    gamma_measured = float(np.median(betas))
    h_rec = hurst_from_gamma(gamma_measured)
    err = abs(h_rec - h_true)
    return CanonicalVerdict(
        h_true=h_true,
        gamma_expected=gamma_expected,
        gamma_measured=gamma_measured,
        h_recovered=h_rec,
        abs_error_h=err,
        passed=bool(err < tol),
    )
