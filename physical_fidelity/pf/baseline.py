"""Baseline measurement of every metric (GAP-O-01 step 7).

Runs the full verifier battery against analytic references and synthetic
canonical benchmarks, then assembles the admissibility ScoreCard S0. This is the
*actual measured baseline* the audit said was missing -- not a target, not a
guess. Run via ``python -m physical_fidelity.pf.baseline``.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from . import dynamics, energy, hypotheses, scoring, spectral, stability, turing


def measure(seed: int = 0) -> scoring.ScoreCard:
    """Measure all metrics and return the populated ScoreCard."""
    card = scoring.ScoreCard()
    rng = np.random.default_rng(seed)

    # --- GeoSync: order-parameter bound (invariant r in [0,1]) ------------- #
    n = 64
    w_complete = np.ones((n, n)) - np.eye(n)
    omega_spread = rng.standard_normal(n)
    res = dynamics.integrate_kuramoto(
        omega_spread, w_complete, k=0.5, t_end=30.0, dt=0.02, seed=seed
    )
    rmax = float(res.r_series.max())
    card.add(
        scoring.MetricResult(
            "order_param_bound",
            rmax,
            1.0,
            scoring.boolean_score(rmax <= 1.0 + 1e-9),
            1.0,
            "ANCHORED",
            "r in [0,1] triangle-inequality invariant",
        )
    )

    # --- GeoSync: identical frequencies synchronize ----------------------- #
    omega_id = np.zeros(n)
    res_sync = dynamics.integrate_kuramoto(
        omega_id, w_complete, k=2.0, t_end=50.0, dt=0.02, seed=seed
    )
    card.add(
        scoring.MetricResult(
            "sync_identical",
            res_sync.r_mean_tail,
            1.0,
            scoring.relative_accuracy_score(res_sync.r_mean_tail, 1.0, tol=0.05),
            1.0,
            "ANCHORED",
            "identical-frequency locked state r->1",
        )
    )

    # --- GeoSync: incoherent floor r ~ (sqrt(pi)/2)/sqrt(N) (K=0 null) ----- #
    res_inc = dynamics.integrate_kuramoto(
        rng.standard_normal(n), w_complete, k=0.0, t_end=30.0, dt=0.02, seed=seed
    )
    ref_floor = dynamics.incoherent_order_parameter_scale(n)
    card.add(
        scoring.MetricResult(
            "incoherent_floor",
            res_inc.r_mean_tail,
            ref_floor,
            scoring.relative_accuracy_score(res_inc.r_mean_tail, ref_floor, tol=0.6),
            0.7,
            "ANCHORED",
            "K=0 null model finite-size order parameter",
        )
    )

    # --- GeoSync: incoherent scaling slope ~ -1/2 ------------------------- #
    ns = np.array([16, 32, 64, 128, 256])
    rs = []
    for nn in ns:
        wc = np.ones((nn, nn)) - np.eye(nn)
        r = dynamics.integrate_kuramoto(
            rng.standard_normal(nn), wc, k=0.0, t_end=20.0, dt=0.02, seed=seed + nn
        )
        rs.append(r.r_mean_tail)
    scaling = hypotheses.test_scaling_exponent(ns, np.array(rs))
    card.add(
        scoring.MetricResult(
            "incoherent_scaling_slope",
            scaling.statistic,
            -0.5,
            scoring.boolean_score(not scaling.reject_h0),
            0.8,
            "ANCHORED",
            "O(1/sqrt N) finite-size scaling law",
        )
    )

    # --- GeoSync: synchronization hypothesis test (reject incoherent null) - #
    r_samples = np.array(
        [
            dynamics.integrate_kuramoto(
                omega_id, w_complete, k=2.0, t_end=40.0, dt=0.02, seed=seed + i
            ).r_final
            for i in range(20)
        ]
    )
    htest = hypotheses.test_synchronization(r_samples)
    card.add(
        scoring.MetricResult(
            "sync_falsification",
            htest.p_value,
            0.05,
            scoring.boolean_score(htest.reject_h0),
            0.6,
            "ANCHORED",
            "KS rejection of r~U(0,1) incoherent null",
        )
    )

    # --- GeoSync/Ricci: total graph weight conservation ------------------- #
    w0 = (rng.random((24, 24)) < 0.3).astype(float)
    w0 = np.triu(w0, 1)
    w0 = w0 + w0.T
    _, totals = dynamics.ricci_flow(w0, steps=40, eps=0.1)
    cons = energy.graph_weight_conservation(totals)
    card.add(
        scoring.MetricResult(
            "ricci_weight_conservation",
            cons.rel_residual,
            0.0,
            scoring.boolean_score(cons.passed),
            1.0,
            "ANCHORED",
            "normalized Ricci flow conserves total weight",
        )
    )

    # --- NFI canonical: gamma_PSD = 2H + 1 -------------------------------- #
    cv = spectral.verify_gamma_2h1(0.75, seed=seed)
    card.add(
        scoring.MetricResult(
            "gamma_2H_plus_1",
            cv.h_recovered,
            cv.h_true,
            scoring.relative_accuracy_score(cv.h_recovered, cv.h_true, tol=0.2),
            1.0,
            "ANCHORED",
            f"gamma={cv.gamma_measured:.3f} -> H_rec={cv.h_recovered:.3f} (NFI canonical contract)",
        )
    )

    # --- MFN: Turing instability in known region + stable control --------- #
    unstable = turing.analyze_schnakenberg(a=0.1, b=0.9, d_u=1.0, d_v=40.0)
    stable = turing.analyze_schnakenberg(
        a=0.1, b=0.9, d_u=1.0, d_v=1.0
    )  # equal diffusion -> no Turing
    turing_ok = unstable.is_turing_unstable and (not stable.is_turing_unstable)
    card.add(
        scoring.MetricResult(
            "turing_schnakenberg",
            float(unstable.max_growth_rate),
            0.0,
            scoring.boolean_score(turing_ok),
            1.0,
            "ANCHORED",
            "Schnakenberg: unstable at D_v/D_u=40, stable at ratio=1",
        )
    )

    # --- MFN: parabolic vs hyperbolic timestep scaling (GAP-M-04) --------- #
    # The real defect: the two limits scale differently (parabolic ~ dx^2,
    # hyperbolic ~ dx), so their ratio is linear in dx. Verify slope ~ 1.
    dxs = np.array([0.2, 0.1, 0.05, 0.025, 0.0125])
    ratios = np.array(
        [stability.compare_cfl_vs_diffusion(dx=dx, c=1.0, d_max=0.01, ndim=2).ratio for dx in dxs]
    )
    dt_slope = float(np.polyfit(np.log(dxs), np.log(ratios), 1)[0])
    card.add(
        scoring.MetricResult(
            "stability_dt_scaling",
            dt_slope,
            1.0,
            scoring.relative_accuracy_score(dt_slope, 1.0, tol=0.1),
            0.5,
            "ANCHORED",
            f"dt_parabolic/dt_hyperbolic ~ dx^{dt_slope:.2f} (parabolic!=hyperbolic)",
        )
    )

    # --- BN-Syn/MFN: regime-conditioned MLE (GAP-M-05) -------------------- #
    omega_chaos = rng.standard_normal(12) * 1.5
    w_small = np.ones((12, 12)) - np.eye(12)

    def rhs_inc(theta: np.ndarray) -> np.ndarray:
        return dynamics.kuramoto_rhs(theta, omega_chaos, 0.2, w_small, 0.0)

    def rhs_lock(theta: np.ndarray) -> np.ndarray:
        return dynamics.kuramoto_rhs(theta, np.zeros(12), 4.0, w_small, 0.0)

    mle_inc = stability.max_lyapunov(
        rhs_inc, rng.uniform(-np.pi, np.pi, 12), n_steps=4000, n_transient=1000
    )
    mle_lock = stability.max_lyapunov(
        rhs_lock, rng.uniform(-np.pi, np.pi, 12), n_steps=4000, n_transient=1000
    )
    regime_ok = (mle_lock < 0.05) and (mle_inc > mle_lock)
    card.add(
        scoring.MetricResult(
            "mle_regime_conditioned",
            mle_lock,
            0.0,
            scoring.boolean_score(regime_ok),
            0.6,
            "ANCHORED",
            f"locked MLE={mle_lock:.3f}<incoherent MLE={mle_inc:.3f}",
        )
    )

    return card


def main() -> None:
    """Run the baseline and emit JSON + a short human report to stdout."""
    card = measure()
    payload: dict[str, Any] = card.to_dict()
    print(json.dumps(payload, indent=2))
    print("\n=== NFI-GAP-001 baseline S0 (ADMISSIBILITY, not a science claim) ===")
    print(f"S0 = {card.score:.2f}/100  over {len(card.metrics)} metrics")
    for m in card.metrics:
        flag = "PASS" if m.score >= 60 else "FAIL"
        print(f"  [{flag}] {m.key:28s} score={m.score:6.2f} w={m.weight}  ({m.tier})")


if __name__ == "__main__":
    main()
