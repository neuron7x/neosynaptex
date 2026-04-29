# Phase 3 — pre-merge smoke run on `serotonergic_kuramoto`

> Status: research-only on the Phase 2.1 work-tree. Not pushed.
> Run: 2026-04-29 ~11:30 EET, machine-local on this branch.

## What was run

```python
SEED = 42
M = 200
adapter = SerotonergicKuramotoAdapter(seed=SEED)
gamma_obs, r2 = _sweep_gamma(adapter)        # canonical sibling pipeline

# 20 (topo, cost) samples across c ∈ [0, 1]
samples = [adapter.sample_at(c) for c in linspace(0, 1, 20)]
topos = array([s["topo"] for s in samples])
costs = array([s["thermo_cost"] for s in samples])

# M IAAFT surrogates of the cost trajectory; topo held fixed
for k in range(M):
    surr, _, _ = iaaft_surrogate(costs, n_iter=200, rng=rng)
    gamma_null[k], _ = _fit_gamma(topos, surr)
```

## Numbers

```
OBSERVED         γ̂ = 1.0677    R² = 0.5826
NULL ENSEMBLE    M_used = 200 / 200
  γ̂_null mean   =  0.0778
  γ̂_null std    =  0.5993
  γ̂_null q025   = -1.0066
  γ̂_null q500   =  0.1777
  γ̂_null q975   =  0.9472
  p (distance-from-γ=1, lower = more separation) = 0.0498
  p (two-tailed |γ| ≥ |γ_obs|)                    = 0.0149
VERDICT (Bonferroni α/2 = 0.025):  NULL_NOT_REJECTED
runtime: 7.38 s
result_hash: 7fc9f4ee3a0aac3ad503e6958d2bbd44…
```

## The interesting finding

The canonical ledger entry for `serotonergic_kuramoto` documents
`p_permutation = 1.0 — null cannot be rejected; surrogate did NOT
distinguish from γ = 1`. **This smoke run gives `p ≈ 0.05` instead.**
That is not a contradiction; it is a *first principle* about Phase 3:

> **The null protocol IS the test.** Different surrogate strategies on
> the same substrate give different p-values, because they preserve
> different structure. Without an explicit, declared null protocol per
> substrate, the verdict is meaningless.

What's different here:

| dimension | canonical p=1.0 entry (ledger v2.0.0) | smoke run (this doc) |
|---|---|---|
| what's surrogated | (unclear from current ledger metadata) | the cost vector, with topo held fixed |
| what's preserved | unclear | (topo, K_eff) sweep + amplitude distribution of cost |
| null mean γ̂ | ≈ 1 (claimed) | 0.08 |
| null spread | tight around 1 (claimed) | wide, σ ≈ 0.6 |

The two nulls test different hypotheses:

* **Cost-IAAFT (this run)** asks: does γ ≈ 1 survive when cost values
  are reshuffled while preserving their power spectrum? → marginal
  rejection at p = 0.05; the topo–cost coupling carries some signal.
* **Trajectory-IAAFT (presumed canonical)** asks: does γ ≈ 1 survive
  when the entire (topo, cost) trajectory is replaced by a random
  Kuramoto trajectory matched in spectrum? → null cannot be rejected.

The Phase 3 PR must:

1. **Pin per-substrate canonical null protocols** in
   `tools/phase_3/family_router.py`. No "default" surrogate — every
   substrate names its families explicitly.
2. **Run the full registered family set** per substrate, with
   Bonferroni correction on the family count.
3. **Reproduce the documented `p = 1.0` ledger entry** as the canonical
   v1 result, OR explicitly retire that entry's claim if the new
   protocol disagrees. Phase 3 must NOT silently overwrite.

## What this confirms

* The `core/iaaft.py::iaaft_surrogate` pipeline works end-to-end on a
  real substrate adapter in 7 seconds for `M = 200`. Scaling to
  `M = 10000` is ~6 min single-core; trivially parallelisable.
* The `_fit_gamma` Theil-Sen-equivalent fit is stable on the
  surrogated data (no NaN drops out of 200 surrogates).
* `result_hash` over the canonicalised summary is deterministic.

## What this does NOT confirm

* That γ ≈ 1 separates signal from null on this substrate. The smoke
  result is borderline (p = 0.05) on a single null family with a
  partial protocol.
* That the documented canonical `p = 1.0` is reproducible. It almost
  certainly came from a different (stronger) null. Phase 3 must
  re-derive it under the canonical protocol or retire the value.
* That the γ ≈ 1.0 universality claim is supported. **It is not.**

## Next concrete step (Phase 3 PR opening day)

After PR #160 merges:

1. Build `tools/phase_3/run_null_screen.py` skeleton (see plan §6).
2. Pin `family_router` for `serotonergic_kuramoto` to
   `["kuramoto_iaaft", "linear_matched", "constrained_randomization"]`.
3. Run `M = 10000` per family.
4. Surface 3 p-values + Bonferroni verdict in `null_family_status`.
5. Compare to the ledger's `p = 1.0` claim; if discrepant, open a
   downgrade PR before any other Phase 3 work.
