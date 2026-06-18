"""Uncertainty quantification with an explicit stochastic model (GAP-E-01).

The Plan proposed Monte-Carlo UQ on a *deterministic* PDE -- which has zero
sampling variance, so every "confidence interval" would be a point. UQ requires
a probability measure over inputs. We make it explicit: a **log-normal parameter
prior** around nominal values, propagated through a deterministic forward map.

    theta_k = theta0_k * LogNormal(0, sigma^2)

This is parametric UQ (Saltelli et al. 2008). The forward map is any callable
returning a scalar observable; we return the empirical 95% CI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


@dataclass(frozen=True)
class UQResult:
    """Empirical UQ summary over a parameter prior."""

    mean: float
    std: float
    ci95: tuple[float, float]
    n_samples: int
    samples: Array


def lognormal_prior_sample(
    nominal: Mapping[str, float], sigma: float, n: int, *, seed: int = 0
) -> list[dict[str, float]]:
    """Draw ``n`` parameter dicts from independent log-normal priors.

    Each parameter k is ``nominal_k * exp(sigma * Z)`` with Z ~ N(0,1). The
    median equals the nominal value; sigma is the multiplicative log-spread,
    set from measurement/literature uncertainty.
    """
    rng = np.random.default_rng(seed)
    keys = list(nominal.keys())
    draws = rng.standard_normal((n, len(keys)))
    out: list[dict[str, float]] = []
    for row in draws:
        out.append(
            {k: float(nominal[k] * np.exp(sigma * z)) for k, z in zip(keys, row, strict=True)}
        )
    return out


def propagate(
    forward: Callable[[Mapping[str, float]], float],
    samples: Sequence[Mapping[str, float]],
) -> UQResult:
    """Propagate a parameter sample through a deterministic forward map."""
    vals = np.array([forward(s) for s in samples], dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return UQResult(
        mean=float(vals.mean()),
        std=float(vals.std(ddof=1)) if vals.size > 1 else 0.0,
        ci95=(float(lo), float(hi)),
        n_samples=int(vals.size),
        samples=vals,
    )


def parametric_uq(
    forward: Callable[[Mapping[str, float]], float],
    nominal: Mapping[str, float],
    *,
    sigma: float = 0.1,
    n: int = 1000,
    seed: int = 0,
) -> UQResult:
    """End-to-end parametric UQ: prior -> forward map -> 95% CI."""
    samples = lognormal_prior_sample(nominal, sigma, n, seed=seed)
    return propagate(forward, samples)


def latin_hypercube(
    nominal: Mapping[str, float], sigma: float, n: int, *, seed: int = 0
) -> list[dict[str, float]]:
    """Latin Hypercube sample of a log-normal prior (NFI-PROMPT-002 Section 6).

    Stratified one-sample-per-bin per dimension -> better space-filling than crude
    Monte Carlo for the small budgets (N=50-200) a solo operator can afford.
    """
    rng = np.random.default_rng(seed)
    keys = list(nominal.keys())
    d = len(keys)
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, d))
    points = cut[:n, None] + u * (1.0 / n)
    for j in range(d):
        rng.shuffle(points[:, j])
    z = _norm_ppf(points)
    return [
        {k: float(nominal[k] * np.exp(sigma * z[i, j])) for j, k in enumerate(keys)}
        for i in range(n)
    ]


def _norm_ppf(p: NDArray[np.float64]) -> NDArray[np.float64]:
    """Inverse standard-normal CDF via scipy (vectorized)."""
    from scipy.special import ndtri

    out: NDArray[np.float64] = np.asarray(ndtri(np.clip(p, 1e-12, 1 - 1e-12)), dtype=np.float64)
    return out


@dataclass(frozen=True)
class SobolResult:
    """First-order Sobol sensitivity indices per parameter."""

    first_order: dict[str, float]
    total_variance: float


def sobol_from_matrices(
    forward: Callable[[Mapping[str, float]], float],
    sa: Sequence[Mapping[str, float]],
    sb: Sequence[Mapping[str, float]],
) -> SobolResult:
    """Saltelli (2010) first-order Sobol indices from two independent samples.

    ``S_i = mean(f_B * (f_AB^i - f_A)) / Var(Y)``, where AB^i is matrix A with its
    i-th column taken from B. Estimator-agnostic to how A, B were drawn (uniform,
    log-normal, LHS), so it is validated on the analytic Ishigami benchmark.
    """
    keys = list(sa[0].keys())
    n = len(sa)
    fa = np.array([forward(s) for s in sa])
    fb = np.array([forward(s) for s in sb])
    var = float(np.var(np.concatenate([fa, fb]), ddof=1))
    indices: dict[str, float] = {}
    for k in keys:
        fab = np.empty(n)
        for i in range(n):
            row = dict(sa[i])
            row[k] = sb[i][k]
            fab[i] = forward(row)
        indices[k] = float(np.mean(fb * (fab - fa)) / var) if var > 0 else 0.0
    return SobolResult(first_order=indices, total_variance=var)


def sobol_first_order(
    forward: Callable[[Mapping[str, float]], float],
    nominal: Mapping[str, float],
    *,
    sigma: float = 0.1,
    n: int = 256,
    seed: int = 0,
) -> SobolResult:
    """First-order Sobol indices under a log-normal parameter prior."""
    sa = lognormal_prior_sample(nominal, sigma, n, seed=seed)
    sb = lognormal_prior_sample(nominal, sigma, n, seed=seed + 99991)
    return sobol_from_matrices(forward, sa, sb)


def uniform_sample(
    bounds: Mapping[str, tuple[float, float]], n: int, *, seed: int = 0
) -> list[dict[str, float]]:
    """Independent uniform sample over per-parameter (lo, hi) bounds."""
    rng = np.random.default_rng(seed)
    keys = list(bounds.keys())
    out: list[dict[str, float]] = []
    for _ in range(n):
        out.append({k: float(rng.uniform(*bounds[k])) for k in keys})
    return out
