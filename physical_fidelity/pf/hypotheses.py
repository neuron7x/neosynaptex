"""Falsification register with explicit H0/H1 (GAP-E-02).

The Plan named "chi^2 and KS tests, alpha=0.05" with no null hypothesis or
reference distribution -- so no test was actually defined. Here each falsifiable
claim carries an explicit (H0, H1, statistic, rejection rule). A *failure to
reject* leaves the model un-promoted; a rejection of the incoherent null is the
only thing that licenses a synchronization claim.

References
----------
* Fisher, R.A. (1925). Statistical Methods for Research Workers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import stats

Array = NDArray[np.float64]


@dataclass(frozen=True)
class HypothesisTest:
    """A pre-registered statistical test outcome."""

    name: str
    h0: str
    h1: str
    statistic: float
    p_value: float
    alpha: float
    reject_h0: bool


def test_synchronization(r_samples: Array, *, alpha: float = 0.05) -> HypothesisTest:
    """GeoSync falsification: is the order parameter beyond the incoherent null?

    H0: r ~ Uniform(0,1)  (no preferred synchronization level)
    H1: r distribution is shifted (KS departure from Uniform)
    Test: one-sample KS of r against U(0,1). Reject H0 => synchronization signal.
    """
    r = np.clip(np.asarray(r_samples, dtype=np.float64), 0.0, 1.0)
    ks = stats.kstest(r, "uniform")
    return HypothesisTest(
        name="geosync_synchronization",
        h0="r ~ Uniform(0,1) (incoherent null)",
        h1="r departs from Uniform(0,1)",
        statistic=float(ks.statistic),
        p_value=float(ks.pvalue),
        alpha=alpha,
        reject_h0=bool(ks.pvalue < alpha),
    )


def test_spectral_peak(
    freqs: Array, power: Array, *, k_band: tuple[float, float], alpha: float = 0.05
) -> HypothesisTest:
    """MFN falsification: is there a dominant Turing wavelength?

    H0: spectral power in the candidate band equals the background floor (flat).
    H1: the band power exceeds the floor (a peak at k_c).
    Test: Welch t-test of in-band vs out-of-band log-power. Reject => pattern.
    """
    f = np.asarray(freqs, dtype=np.float64)
    p = np.log(np.asarray(power, dtype=np.float64) + 1e-30)
    in_band = (f >= k_band[0]) & (f <= k_band[1])
    out_band = ~in_band
    if in_band.sum() < 2 or out_band.sum() < 2:
        raise ValueError("insufficient samples in/out of band")
    t = stats.ttest_ind(p[in_band], p[out_band], equal_var=False, alternative="greater")
    return HypothesisTest(
        name="mfn_turing_peak",
        h0="in-band power == background floor (no pattern)",
        h1="in-band power > floor (Turing peak)",
        statistic=float(t.statistic),
        p_value=float(t.pvalue),
        alpha=alpha,
        reject_h0=bool(t.pvalue < alpha),
    )


def test_scaling_exponent(
    n_values: Array, r_values: Array, *, expected: float = -0.5, tol: float = 0.12
) -> HypothesisTest:
    """GeoSync finite-size falsification: does incoherent r scale as N^{-1/2}?

    H0: log r vs log N slope == expected (-0.5, the O(1/sqrt N) law)
    H1: slope != expected
    Test: |fitted slope - expected| < tol  => fail to reject H0 (law holds).
    """
    ln_n = np.log(np.asarray(n_values, dtype=np.float64))
    ln_r = np.log(np.asarray(r_values, dtype=np.float64))
    slope, intercept = np.polyfit(ln_n, ln_r, 1)
    deviation = abs(float(slope) - expected)
    return HypothesisTest(
        name="geosync_incoherent_scaling",
        h0=f"slope == {expected} (O(1/sqrt N) incoherent law)",
        h1=f"slope != {expected}",
        statistic=float(slope),
        p_value=float("nan"),
        alpha=tol,
        reject_h0=bool(deviation > tol),
    )
