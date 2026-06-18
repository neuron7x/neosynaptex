# UQ plan (tool 10) — stochastic source defined BEFORE Monte Carlo

Forbidden: Monte Carlo on a deterministic model (zero-width CI). Source chosen:
**A. parameter prior** — log-normal multiplicative, σ from literature/10% nominal.
Code `pf/uq.py`; tests `tests/physics/test_uq_smoke.py`.

| parameter | nominal | distribution | reason | observable | expected sensitivity |
|-----------|--------:|--------------|--------|------------|----------------------|
| K (coupling) | 1.5 | LogNormal(0,0.1²) | calibration spread | r(∞) | high near K_c |
| τ_w (adaptation) | 144 ms | LogNormal(0,0.1²) | Brette-Gerstner range | ISI CV | moderate |
| D_v/D_u (MFN) | 40 | LogNormal(0,0.1²) | Turing regime width | k_c | high near threshold |

Method (solo): Latin Hypercube N=50–200 (`uq.latin_hypercube`); first-order Sobol
(`uq.sobol_from_matrices`, validated on Ishigami: S1=0.32 vs 0.314, S2=0.46 vs 0.442).
CI(95%) emitted only where a stochastic source exists.
