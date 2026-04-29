"""Cohen's d effect size + bootstrap CI on d.

Phase 3 reports Cohen's d for the gap between observed γ and the null
γ̂ ensemble. The reference distribution under H_0 is the null ensemble
itself, so the formula reduces to

    d = (γ̂_obs - mean(γ̂_null)) / std(γ̂_null)

The CI on d is computed by non-parametric bootstrap of the null
ensemble (B replicates, default 1000) — the observed γ is treated as a
fixed scalar (no bootstrap on the single point estimate).
"""

from __future__ import annotations

import dataclasses

import numpy as np

__all__ = [
    "EffectSize",
    "cohen_d_with_bootstrap_ci",
]


@dataclasses.dataclass(frozen=True)
class EffectSize:
    """Cohen's d + bootstrap CI on d.

    Attributes
    ----------
    d : float
        Cohen's d. Positive ⇒ observed γ is above null mean.
        ``nan`` when the null ensemble has zero variance (degenerate).
    ci95_low, ci95_high : float
        95 % bootstrap CI on d. ``nan`` when the bootstrap cannot
        be evaluated (n_null < 2 or zero-variance ensemble).
    n_null : int
        Number of admissible (finite) null γ values used.
    n_bootstrap : int
        Number of bootstrap replicates that contributed to the CI.
    degenerate : bool
        True if the null ensemble was constant or empty.
    """

    d: float
    ci95_low: float
    ci95_high: float
    n_null: int
    n_bootstrap: int
    degenerate: bool


_MIN_NULL: int = 2


def cohen_d_with_bootstrap_ci(
    gamma_obs: float,
    gamma_null: np.ndarray,
    *,
    n_bootstrap: int = 1000,
    seed: int | None = None,
) -> EffectSize:
    """Compute Cohen's d of ``gamma_obs`` vs the ``gamma_null`` ensemble.

    Parameters
    ----------
    gamma_obs : float
        Observed γ (scalar). NaN propagates to a degenerate result.
    gamma_null : np.ndarray
        1-D array of γ̂ values under the null. NaN entries are
        dropped before estimation.
    n_bootstrap : int
        Number of bootstrap replicates. Must be ``> 0``.
    seed : int, optional
        Bootstrap RNG seed. Required when callers need reproducibility.
    """
    if n_bootstrap <= 0:
        raise ValueError(f"n_bootstrap must be positive; got {n_bootstrap}")

    null = np.asarray(gamma_null, dtype=np.float64).ravel()
    null = null[np.isfinite(null)]
    n_null = int(null.size)

    if not np.isfinite(gamma_obs) or n_null < _MIN_NULL:
        return EffectSize(
            d=float("nan"),
            ci95_low=float("nan"),
            ci95_high=float("nan"),
            n_null=n_null,
            n_bootstrap=0,
            degenerate=True,
        )

    mean_null = float(np.mean(null))
    std_null = float(np.std(null, ddof=1))
    if std_null < 1e-15:
        return EffectSize(
            d=float("nan"),
            ci95_low=float("nan"),
            ci95_high=float("nan"),
            n_null=n_null,
            n_bootstrap=0,
            degenerate=True,
        )

    d_point = (float(gamma_obs) - mean_null) / std_null

    rng = np.random.default_rng(seed)
    boot_d = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n_null, size=n_null)
        sample = null[idx]
        s_mean = float(np.mean(sample))
        s_std = float(np.std(sample, ddof=1))
        if s_std < 1e-15:
            boot_d[i] = float("nan")
        else:
            boot_d[i] = (float(gamma_obs) - s_mean) / s_std

    boot_d_finite = boot_d[np.isfinite(boot_d)]
    if boot_d_finite.size < 2:
        return EffectSize(
            d=d_point,
            ci95_low=float("nan"),
            ci95_high=float("nan"),
            n_null=n_null,
            n_bootstrap=int(boot_d_finite.size),
            degenerate=False,
        )

    lo, hi = np.quantile(boot_d_finite, [0.025, 0.975])
    return EffectSize(
        d=d_point,
        ci95_low=float(lo),
        ci95_high=float(hi),
        n_null=n_null,
        n_bootstrap=int(boot_d_finite.size),
        degenerate=False,
    )
