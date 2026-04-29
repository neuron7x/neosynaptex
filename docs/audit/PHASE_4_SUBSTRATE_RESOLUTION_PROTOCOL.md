# Phase 4 — Substrate Resolution Protocol

**Status:** frozen — content changes require a protocol-version bump.
**Authoritative implementation:** `substrates/serotonergic_kuramoto/adapter.py` (v2.0.0).
**Authoritative test battery:** `tests/test_substrate_serotonergic_kuramoto_v2.py`.
**Predecessors:** PR #161 (Estimator Admissibility, Phase 3 P0); Phase 3 null-screen runner.

## 1. Why this PR exists

The Phase 3 estimator-admissibility trial (PR #161, reference verdict
`result_hash: ed619996…`) accepted the canonical Theil–Sen γ-estimator
under the condition `MIN_TRAJECTORY_LENGTH = 128`. The
`serotonergic_kuramoto` substrate adapter, however, has been emitting a
trajectory of length `_N_SWEEP = 20` — structurally below the
admissibility floor. Under Phase 3's null-screen runner that adapter's
γ̂ landed `ESTIMATOR_ARTIFACT_SUSPECTED` because the operator was being
asked to measure with fewer samples than its admissibility certificate
required.

Phase 4 fixes the substrate. It does **not** touch the estimator. The
estimator already passed at N ≥ 128; the substrate is the asymmetric
half of the contract. Once the substrate emits N ≥ 128 log-uniformly
spaced concentration samples, the canonical Phase 3 null-screen
protocol can be run again and a meaningful verdict can be emitted.

## 2. What changes (the three coupled changes)

1. `tools/phase_3/admissibility/__init__.py` — new public constant
   `MIN_TRAJECTORY_LENGTH: Final[int] = 128`, exported in `__all__`.
   This is the canonical reference downstream substrate adapters must
   respect.

2. `substrates/serotonergic_kuramoto/adapter.py` (v2.0.0):
   - `_N_SWEEP = 20` → `_N_SWEEP: Final[int] = 128`. Module-level
     assertion against `MIN_TRAJECTORY_LENGTH`.
   - `_SWEEP_MIN = 0.0` → `_SWEEP_MIN = 0.01`. Strictly positive
     required by `np.geomspace`; `c = 0` is unphysical for the
     `K ~ C^(-γ)` log–log fit (`log(0) = -inf` is dropped by the
     estimator's finite-filter anyway).
   - `np.linspace(...)` → `np.geomspace(...)`. Linear-c sampling biases
     the log–log regression toward the high-c decade; log-uniform
     spreads samples evenly across the regression target.
   - Module-level `__version__: Final[str] = "2.0.0"`.

3. `tests/test_substrate_serotonergic_kuramoto_v2.py` — six regression
   tests covering the admissibility floor, log-uniformity of the
   `c` grid, intended range, version bump, sample-at smoke at the new
   grid, and the SHA-256 invalidation of any v1 ledger
   `hash_binding`.

## 3. What does NOT change

- `tools/phase_3/estimator.py` — the canonical Theil–Sen γ-estimator
  is left bit-identical. Phase 3's admissibility trial accepted it.
- `evidence/gamma_ledger.json` — Phase 4 is a substrate fix; ledger
  mutation is a separate proposal-only PR with the new γ̂_obs from
  the Phase 3 null-screen runner re-executed at M=10000.
- `CANON_VALIDATED_FROZEN` — stays `True`.
- `tools/phase_3/admissibility/` — only the `MIN_TRAJECTORY_LENGTH`
  constant is added to `__init__.py`; the trial logic, metrics, and
  verdict module are untouched.
- `tools/phase_3/run_null_screen.py` — runner unchanged.
- Other substrate adapters — only `serotonergic_kuramoto` is touched.

## 4. Expected outcome under canonical Phase 3 null-screen at M=10000

The canonical Phase 3 null-screen runner is to be re-executed against
the v2 adapter at the precision-floor `M = 10000` and per-family
Bonferroni `α/3 = 0.0167` (3 null families). Two outcomes are
admissible:

- If γ̂_obs at N=128 log-uniform still falls inside the null
  distribution → ledger proposal:
  `EVIDENCE_CANDIDATE_NULL_FAILED`, reason `NULL_NOT_REJECTED`.
- If γ̂_obs separates from null at all 3 families with Bonferroni
  `α/3 = 0.0167` → ledger proposal: `SUPPORTED_BY_NULLS` (the maximum
  admissible label under the closed verdict ladder).

Any other label is forbidden by the closed verdict ladder.

## 5. Forbidden softening words

The following words and phrases must not appear in this protocol, the
adapter, the test battery, or any artefact bound to Phase 4:

- `validated` / `hypothesis validated`
- `cryptographic evidence chain`
- `proven`
- `confirmed by null`
- `causally established`
- `definitive`
- `breakthrough`

## 6. Reproducibility command

```
python -m tools.phase_3.run_null_screen \
  --substrate serotonergic_kuramoto \
  --M 10000 \
  --out evidence/phase_3_null_screen/serotonergic_kuramoto_v2.json
```

PR-time CI smoke (under the precision floor — only allowed under
explicit `--smoke`):

```
python -m tools.phase_3.run_null_screen \
  --substrate serotonergic_kuramoto --M 200 --smoke \
  --out /tmp/phase4_serotonergic_smoke.json
```

## 7. Phase 2.1 binding-gate interaction

Phase 2.1 PR #160 introduced a runtime hash-binding gate
(`core/gamma_registry.py::_load`) that refuses to load
`evidence/gamma_ledger.json` if any entry's stored
`adapter_code_hash` drifts from the on-disk SHA-256 of the named
adapter source. The Phase 4 substrate change *intentionally* drifts
the SHA-256 of `substrates/serotonergic_kuramoto/adapter.py` from
the v1 hash recorded in the ledger
(`df55071e…` → `ce453b1f…`).

This is the system working as designed. The gate signals: the v1
γ̂_obs in the ledger is no longer a valid measurement of the v2
adapter. Until the separate proposal-only PR lands the v2 ledger
update (new `adapter_code_hash`, new γ̂_obs from the canonical
Phase 3 null-screen runner at M=10000), any code path that
imports `core/__init__.py` will fail closed at the binding-gate
check. This includes `pytest` runs through the repository
`tests/conftest.py`.

To verify this branch's invariants standalone, the new substrate
test battery (`tests/test_substrate_serotonergic_kuramoto_v2.py`)
is `--noconftest`-clean and asserts the six Phase 4 invariants
without going through the gate.

## 8. Smoke result (43.5 s wall-clock at the v2 grid)

```
N_sweep                          : 128
c_grid_first / c_grid_last       : 0.01 / 1.0   (log-uniform = True)
sample_at(0.5)                   : topo=1104.5,  thermo_cost=22.40

γ̂_obs (v2, sweep_gamma OLS)      : 0.7403   (R² = 0.5633)
γ̂_obs (v2, Theil-Sen full N=128) : 0.0661

γ̂_obs (v1, ledger reference)     : 1.0677   (R² = 0.5826)

adapter v2 SHA-256               : ce453b1f81120b62…
adapter v1 SHA-256 (ledger ref)  : df55071e0dc8c2f1…
```

Two estimators applied to the same v2 trajectory diverge: the
adapter's internal sorted-OLS fit (`_fit_gamma`) gives γ̂ = 0.74
(consistent with critical-regime metastability), while the
Phase 3-canonical Theil–Sen fit on log(C) → log(K) gives γ̂ = 0.07
(near-flat scaling). The Phase 3 estimator is the canonical one
(only path admitted by the admissibility trial); the divergence
will be carried through the M=10000 null-screen verdict in the
follow-up ledger PR. No softening claim is admitted here.
