# G0 — instrument on ground truth: pre-registration

claim_status: hypothesized

Written and committed **before** the harness exists and before any run. The
commit that adds this file contains nothing else. Stage G0 of
`docs/RESEARCH_DIRECTION.md`.

## Question

Does any candidate statistic (a) track a controlled distance to an analytically
known critical point, (b) carry information beyond the linear spectrum near that
point, and (c) stay silent on linear non-critical processes?

## Simulators (critical point known in closed form)

**S-KUR — noisy mean-field Kuramoto, identical oscillators.**
dθ_i = K·R·sin(ψ − θ_i) dt + √(2D) dW_i, with R·e^{iψ} = mean(e^{iθ}).
Critical coupling K_c = 2D. Fixed: N = 500, D = 0.5 (K_c = 1.0),
Euler–Maruyama dt = 0.05, burn-in 2000 steps, then R sampled every 4th step.
Observable: R(t).

**S-BR — branching process with immigration.**
A_{t+1} ~ Poisson(σ·A_t + h). Critical branching ratio σ_c = 1. Fixed: h = 1.0,
A_0 = round(h/(1−σ)), burn-in 2000 steps. Observable: A(t).

Both: series length n = 4096.

Control grid (subcritical approach), p/p_c ∈ {0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.98}.
Distance d = 1 − p/p_c.

## Linear non-critical generators (specificity side)

AR(1) with φ = 0.9, and linear power-law noise with β = 1.0 (random phases),
n = 4096 — the two spectral generators that reached the METASTABLE band in
`results/gamma_specificity/run_v1.json`.

## Candidate statistics

| id | statistic | fixed parameters |
|---|---|---|
| `trev` | time-reversal asymmetry, mean((x_{t+1} − x_t)^3) / mean((x_{t+1} − x_t)^2)^{3/2} | lag 1 |
| `pe` | normalised permutation entropy | order 4, delay 1, ties broken by position |
| `lzc` | Lempel–Ziv (1976) complexity of the median-binarised series, normalised by n / log2(n) | — |
| `gamma` | spectral slope, `fit_hrv_gamma` after the RR mapping used in the specificity probe | repo defaults, bootstrap off |

`gamma` is included as a **negative control of the method**: IAAFT preserves the
power spectrum, so `gamma` is expected to fail criterion (b). If `gamma` passes
(b), the surrogate machinery is broken and the whole run is void.

## Surrogates

`core.iaaft.iaaft_surrogate`, repo defaults, M = 99 per series. Two-sided rank
p-value of the original among the 100 values; minimum attainable p = 0.02.

## Seeds

Master seed 20261012; 10 independent seeds per condition, derived as
`default_rng([20261012, simulator_index, grid_index, seed_index])`.
A pilot at reduced size (2 seeds, M = 19) under master seed 999 is allowed for
debugging the harness only; its numbers are not evidence and are not committed.

## Criteria — fixed now

For a statistic on one simulator:

- **(a) tracking.** Per seed, Spearman ρ between d and the statistic over the 7
  grid points. Pass: median |ρ| ≥ 0.90 across the 10 seeds **and** the same sign
  of ρ in all 10 seeds.
- **(b) beyond the spectrum.** At p/p_c = 0.98, IAAFT p ≤ 0.02 in at least 8 of
  10 seeds.
- **(c) silence on linear processes.** On each linear generator, IAAFT p ≤ 0.02
  in at most 1 of 10 seeds.

A statistic **passes G0** only if (a) and (b) hold on **both** simulators and
(c) holds on **both** linear generators.

Reported for information, with no bearing on the verdict: the (b) rejection
count at p/p_c = 0.50.

## Verdicts

- `G0_PASS` — at least one of `trev`, `pe`, `lzc` passes.
- `G0_FAIL` — none passes. Per `docs/RESEARCH_DIRECTION.md` the programme stops
  here and the negative is recorded.
- `VOID_METHOD` — `gamma` passes (b) on either simulator.

## What will not be done after seeing the output

No change to thresholds, grid, statistics, parameters, seeds or n. A second
version, if ever run, gets a new file name, a new pre-registration, and is
reported next to this one, not instead of it.

## Known limits, stated in advance

- Subcritical approach only; nothing is claimed about the supercritical side.
- Finite size: N = 500 and n = 4096; at p/p_c = 0.98 the Kuramoto relaxation
  time is about 100 time units, so the window holds roughly 8 of them.
- (b) shows nonlinearity near the critical point, not that nonlinearity is
  caused by criticality; that is why (a) and the p/p_c = 0.50 count are reported.
- Two simulators are not "critical systems in general".
