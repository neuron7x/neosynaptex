"""Falsification stress tests — proving γ breaks when it should.

These tests are the **negative controls** for the γ ≈ 1 claim. Each
assertion takes a signal that the system is ready to identify as
metastable, destroys some part of its structure, and checks that γ
*leaves* the metastable window. A passing test here is a green
signal of rigour: the γ machinery is detecting real structure, not
finding 1.0 everywhere.

Catalogue
---------
1. **Shuffled-topo control** — break the (topo, cost) pairing. γ must
   drift away from 1.0 (or become statistically indistinguishable
   from the null).
2. **Random-cost control** — replace cost with uniform noise. The
   log-log fit must collapse in R² and γ must leave the window.
3. **Brownian 1/f² control** — feed a synthetic signal with known
   γ = 2 (Brownian motion spectral slope). The system must return
   γ ≈ 2, NOT γ ≈ 1.
4. **Per-substrate shuffle** — for each substrate whose adapter we
   can run locally, take its (topo, cost) arrays and destroy the
   ordering. γ must break.

The tests are intentionally **permissive on the failure mode** —
they pass if *any* of: γ leaves [0.7, 1.3], R² drops below a loose
threshold, or p_permutation exceeds 0.1. This leaves room for the
different substrates' signal-to-noise levels while still catching a
system that "finds γ ≈ 1 in anything".
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.bootstrap import permutation_p_value
from core.gamma import compute_gamma


def _gamma_broken(result, ref: float = 1.0, band: tuple[float, float] = (0.7, 1.3)) -> bool:
    """Predicate: γ is either outside the [ref ± band/2] window OR the fit
    itself was rejected (LOW_R2, INSUFFICIENT_*)."""
    if result.verdict in ("LOW_R2", "INSUFFICIENT_DATA", "INSUFFICIENT_RANGE"):
        return True
    if not math.isfinite(result.gamma):
        return True
    return not (band[0] <= result.gamma <= band[1])


# ---------------------------------------------------------------------------
# 1. Shuffled-topo control — clean γ ≈ 1 signal with the pairing destroyed
# ---------------------------------------------------------------------------
def test_gamma_breaks_under_shuffled_topo():
    rng = np.random.default_rng(42)
    # Clean power-law cost ∝ topo^(-1) — would give γ ≈ 1
    topo = np.geomspace(1.0, 100.0, 80)
    cost = topo**-1.0 * np.exp(rng.normal(0, 0.02, topo.size))
    # Sanity: the UNSHUFFLED signal should cleanly identify γ ≈ 1
    baseline = compute_gamma(topo, cost, seed=42)
    assert 0.9 <= baseline.gamma <= 1.1, (
        f"baseline γ={baseline.gamma:.4f} not near 1 — test setup broken"
    )
    assert baseline.verdict == "METASTABLE"
    # Break pairing: shuffle topo, keep cost
    topo_shuffled = rng.permutation(topo)
    broken = compute_gamma(topo_shuffled, cost, seed=42)
    assert _gamma_broken(broken), (
        f"γ survived topo shuffle: γ={broken.gamma:.4f} R²={broken.r2:.4f} verdict={broken.verdict}"
    )


# ---------------------------------------------------------------------------
# 2. Random-cost control
# ---------------------------------------------------------------------------
def test_gamma_breaks_under_random_cost():
    rng = np.random.default_rng(7)
    topo = np.geomspace(1.0, 100.0, 80)
    cost = np.exp(rng.uniform(-2.0, 2.0, topo.size))  # uniform log-space noise
    broken = compute_gamma(topo, cost, seed=42)
    assert _gamma_broken(broken), (
        f"γ held up against random cost: γ={broken.gamma:.4f} "
        f"R²={broken.r2:.4f} verdict={broken.verdict}"
    )


# ---------------------------------------------------------------------------
# 3. Brownian 1/f² control — known γ = 2, must NOT report γ ≈ 1
# ---------------------------------------------------------------------------
@pytest.mark.slow  # 123 s measured locally; exceeds the 120 s cap of the Benchmark job
def test_brownian_1_over_f_squared_reports_gamma_near_2():
    """Synthetic Brownian motion has a PSD ∝ 1/f². Mapping that to
    (topo, cost) = (f, PSD) should give γ = 2, not 1."""
    rng = np.random.default_rng(11)
    n = 4096
    # Brownian = cumulative Gaussian steps
    x = np.cumsum(rng.normal(0, 1, n))
    freqs = np.fft.rfftfreq(n, d=1.0)
    psd = np.abs(np.fft.rfft(x)) ** 2
    # Drop DC + very lowest bins
    mask = freqs > 1e-3
    f = freqs[mask]
    p = psd[mask] + 1e-12
    result = compute_gamma(f, p, seed=42)
    # Brownian PSD ∝ 1/f² → compute_gamma defines γ as −slope of
    # log(cost) vs log(topo), so γ ≈ 2 (not ≈ 1).
    assert math.isfinite(result.gamma)
    assert result.gamma > 1.5, f"Brownian control γ={result.gamma:.4f} — expected ≈ 2, not near 1"
    # Explicitly NOT in the metastable band
    assert result.verdict != "METASTABLE", (
        f"Brownian 1/f² unexpectedly METASTABLE: γ={result.gamma:.4f}"
    )


# ---------------------------------------------------------------------------
# 4. Permutation p-value — proves the null hypothesis is not trivially rejected
# ---------------------------------------------------------------------------
def test_permutation_rejects_pure_noise():
    rng = np.random.default_rng(33)
    topo = np.exp(rng.uniform(0.0, 3.0, 80))
    cost = np.exp(rng.uniform(0.0, 3.0, 80))
    p = permutation_p_value(topo, cost, n_perm=200, seed=42)
    # Pure noise: the observed |γ − 1| is not unusually large vs shuffled
    assert 0.0 <= p <= 1.0
    assert p > 0.05, f"pure noise achieved p={p:.4f} ≤ 0.05 — the test would false-positive"


# ---------------------------------------------------------------------------
# 5. Per-substrate shuffle — serotonergic_kuramoto
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_serotonergic_gamma_breaks_under_shuffled_topo():
    """Shuffling the topo array across the serotonergic sweep points
    must destroy the log-log scaling."""
    from substrates.serotonergic_kuramoto.adapter import (
        SerotonergicKuramotoAdapter,
        _fit_gamma,
    )

    adapter = SerotonergicKuramotoAdapter(concentration=0.5, seed=42)
    topos = np.array([s["topo"] for s in adapter._samples])
    costs = np.array([s["thermo_cost"] for s in adapter._samples])

    # Baseline from the real sweep
    gamma_ref, _ = _fit_gamma(topos, costs)
    assert math.isfinite(gamma_ref)

    # Shuffle topo — break the sweep ordering
    rng = np.random.default_rng(7)
    topos_shuffled = rng.permutation(topos)
    gamma_shuffled, r2_shuffled = _fit_gamma(topos_shuffled, costs)
    print(
        f"[serotonergic shuffle] γ_ref={gamma_ref:.4f} → "
        f"γ_shuffled={gamma_shuffled:.4f}  R²_shuffled={r2_shuffled:.4f}"
    )
    # Shuffle must either move γ outside [0.7, 1.3] or collapse R²
    broken = (not (0.7 <= gamma_shuffled <= 1.3)) or r2_shuffled < 0.3
    assert broken, (
        f"shuffled serotonergic γ={gamma_shuffled:.4f} "
        f"R²={r2_shuffled:.4f} — structure survived shuffle"
    )


# ---------------------------------------------------------------------------
# 6. Per-substrate shuffle — gray_scott
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_gray_scott_gamma_breaks_under_shuffled_topo():
    """Gray-Scott F-sweep: shuffling must destroy the log-log signal."""
    from substrates.gray_scott.adapter import GrayScottAdapter

    adapter = GrayScottAdapter(seed=42)
    topos: list[float] = []
    costs: list[float] = []
    for _ in range(len(adapter._equilibria) * 3):
        adapter.state()
        t = adapter.topo()
        c = adapter.thermo_cost()
        if t > 1e-6 and c > 1e-6:
            topos.append(t)
            costs.append(c)

    t_arr = np.array(topos)
    c_arr = np.array(costs)

    baseline = compute_gamma(t_arr, c_arr, seed=42)
    assert baseline.verdict == "METASTABLE", (
        f"baseline gray_scott verdict={baseline.verdict} — setup off"
    )

    rng = np.random.default_rng(9)
    shuffled = rng.permutation(t_arr)
    broken = compute_gamma(shuffled, c_arr, seed=42)
    print(
        f"[gray_scott shuffle] γ_ref={baseline.gamma:.4f} → "
        f"γ_shuffled={broken.gamma:.4f}  verdict={broken.verdict}"
    )
    assert _gamma_broken(broken), (
        f"gray_scott survived shuffle: γ={broken.gamma:.4f} verdict={broken.verdict}"
    )


# ---------------------------------------------------------------------------
# 7. Per-substrate shuffle — kuramoto_market
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_kuramoto_market_gamma_breaks_under_shuffled_topo():
    from substrates.kuramoto.adapter import KuramotoAdapter

    adapter = KuramotoAdapter(seed=42)
    topos: list[float] = []
    costs: list[float] = []
    for _ in range(300):
        adapter.state()
        t = adapter.topo()
        c = adapter.thermo_cost()
        if t > 1e-6 and c > 1e-6:
            topos.append(t)
            costs.append(c)

    t_arr = np.array(topos)
    c_arr = np.array(costs)
    baseline = compute_gamma(t_arr, c_arr, seed=42)

    rng = np.random.default_rng(13)
    shuffled = rng.permutation(t_arr)
    broken = compute_gamma(shuffled, c_arr, seed=42)
    print(
        f"[kuramoto shuffle] γ_ref={baseline.gamma:.4f} verdict={baseline.verdict} → "
        f"γ_shuffled={broken.gamma:.4f} verdict={broken.verdict}"
    )
    assert _gamma_broken(broken), (
        f"kuramoto survived shuffle: γ={broken.gamma:.4f} verdict={broken.verdict}"
    )


# ---------------------------------------------------------------------------
# 8. Explicit non-power-law — exponential decay cost(topo) = e^{-topo}
# ---------------------------------------------------------------------------
def test_exponential_decay_not_metastable():
    """An exponentially-decaying cost is NOT a power law. The engine
    must flag it (low R² or γ outside window)."""
    rng = np.random.default_rng(5)
    topo = np.linspace(1.0, 50.0, 100)
    cost = np.exp(-0.1 * topo) + rng.normal(0, 0.001, topo.size)
    cost = np.maximum(cost, 1e-6)
    result = compute_gamma(topo, cost, seed=42)
    print(f"[exp decay] γ={result.gamma:.4f} R²={result.r2:.4f} verdict={result.verdict}")
    assert _gamma_broken(result), (
        f"exp decay passed as metastable: γ={result.gamma:.4f} verdict={result.verdict}"
    )
