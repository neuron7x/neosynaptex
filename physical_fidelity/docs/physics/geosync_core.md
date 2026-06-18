# GeoSync — canonical mathematical object

**Decision: A (pure graph Kuramoto) is FIXED.** Ricci coupling is retained only as
a weight-evolution layer with a *proven conservation invariant*; the
manifold-PDE Ricci-flow (Decision B) is **not** promoted — it stays an
admissibility experiment until well-posedness of the coupled system is proven.

## Phase dynamics

```
dθ_i/dt = ω_i + (K / d_i) · Σ_j w_ij(t) · sin(θ_j − θ_i − α)
```

* `d_i = Σ_j w_ij` weighted degree; `α` optional Sakaguchi phase lag (default 0).
* Code: `pf/dynamics.py::kuramoto_rhs`, integrator `integrate_kuramoto` (RK4).

## Order parameter

```
r(t) = | (1/N) Σ_j exp(i θ_j) |   ∈ [0, 1]   (triangle inequality)
```

Code `pf/dynamics.py::order_parameter`; invariant test
`tests/test_protocol.py::test_order_parameter_bounded`.

## Critical coupling (analytic baselines)

* All-to-all, Lorentzian g(ω) half-width γ: `K_c = 2/(π g(0)) = 2γ`
  (`mean_field_critical_coupling_lorentzian`, Kuramoto 1984).
* Graph connectivity bound: `K_c ≤ 2(ω_max−ω_min)/λ₂(L)` where λ₂ is the
  **Fiedler value** (`dorfler_bullo_sync_bound`). NB: λ_min(L)=0 identically, so
  the audit's `2ω_max/λ_min` is singular — corrected here to λ₂ (Dörfler & Bullo 2014).

## Discrete Ricci flow (weight layer)

```
w_ij ← w_ij (1 − ε κ_ij)        (flow; κ = Ollivier–Lin curvature proxy)
w_ij ← w_ij · (W₀ / Σ w)        (renormalize ⇒ Σ w conserved)
```

Conservation invariant proven by `tests/test_protocol.py::test_ricci_flow_conserves_total_weight`.
Well-posedness: w∈[0,W₀] bounded ⇒ Kuramoto RHS globally Lipschitz ⇒ unique IVP solution.

## Primary NFI observable

```
γ_PSD from Welch PSD of r(t);   γ = 2H + 1   (fBm spectral identity)
Test: |γ_measured − (2H_theory + 1)| < ε
```

Code `pf/spectral.py::verify_gamma_2h1`; test `test_gamma_2h1_recovers_hurst`.

## Lyapunov expectations (regime-conditioned)

| Regime | Condition | Expected MLE |
|--------|-----------|--------------|
| sub-sync | K < K_c | > 0 |
| super-sync | K > K_c | < 0 |
| finite-N critical | K ≈ K_c | → 0 only as N → ∞ |

## References
Kuramoto 1984; Dörfler & Bullo 2014; Ollivier 2009; Ni et al. 2019; Flandrin 1989.
