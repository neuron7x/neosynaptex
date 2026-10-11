# M-Invariant M2 Bridge Recovery Roadmap

claim_status: derived
authority: [PR #171](https://github.com/neuron7xLab/neosynaptex/pull/171) `INVALID_HWI` verdict, merge commit `27fc29a`
last_updated: 2026-05-01
parent_doc: [`docs/reports/M_INVARIANT_BRIDGE_STATUS.md`](../reports/M_INVARIANT_BRIDGE_STATUS.md)
machine_registry: [`contracts/M_BRIDGE_CLAIM_STATUS.yaml`](../../contracts/M_BRIDGE_CLAIM_STATUS.yaml)

## Why this exists

The default failure mode after a falsification is **one bloated PR** that
mixes design, operator changes, contract amendments, measurement, and
claim mutation. That makes it impossible for a reviewer to tell which
piece survived which gate. This roadmap forbids that.

## Single rule

> The next valid scientific move is not to prove the bridge.
> The next valid scientific move is to prevent the wrong bridge from
> ever being mistaken for proof again.

Each PR below has a single responsibility and a hard merge gate. No
PR may introduce both design AND measurement.

## Seven-PR split

### PR M2.1 — Status Freeze + Claim Registry + Lint + Roadmap (this PR)

| field | value |
|---|---|
| Adds | `docs/reports/M_INVARIANT_BRIDGE_STATUS.md`, `contracts/M_BRIDGE_CLAIM_STATUS.yaml`, `tools/audit/m_bridge_claim_lint.py`, `tests/test_m_bridge_claim_status.py`, this roadmap |
| Modifies | nothing in `core/`, `substrates/`, `manuscript/`, `evidence/`, gamma_ledger |
| Asserts | none beyond the `INVALID_HWI` verdict already merged in #171 |
| Forbidden | claim mutation, threshold change, measurement |
| Merge gate | tests pass; lint passes on its own repo state; CI green |

### PR M2.2 — HWI Scale-Dependence Diagnostics

| field | value |
|---|---|
| Adds | `experiments/m_invariant_scale_diagnostics/run.py`, `README.md`, `tests/test_m_invariant_scale_diagnostics.py`, `results/m_invariant_scale_diagnostics/run_v1.json` |
| Modifies | nothing in `core/`, `substrates/`, manuscript |
| Asserts | one of `SCALE_DEPENDENT` / `SCALE_STABLE` / `INVALID_OPERATOR` on synthetic distributions only |
| Forbidden | any substrate measurement, any bridge claim, modification of M_BRIDGE_CLAIM_STATUS |
| Merge gate | deterministic output; at least one synthetic case shows M changes under coordinate rescaling; clamp saturation detected; tests pass |

### PR M2.3 — BN-Syn Spatial Embedding Design (no measurement)

| field | value |
|---|---|
| Adds | `docs/design/BNSYN_SPATIAL_EMBEDDING_FOR_HWI.md` |
| Modifies | nothing executable |
| Asserts | recommended embedding candidate + fallback; falsification conditions for each |
| Forbidden | any embedding implementation in `substrates/bn_syn/`, any measurement, any code that loads BN-Syn dynamics |
| Merge gate | doc exists; covers ring / 2-D sheet / spectral / random-geometric; per-candidate definition + null model + failure mode + required tests; recommends one primary + one fallback |

### PR M2.4 — Scale-Invariant Operator Candidates Design (no measurement)

| field | value |
|---|---|
| Adds | `docs/design/SCALE_INVARIANT_BRIDGE_OPERATORS.md` |
| Modifies | nothing executable |
| Asserts | candidate operator classes (≤5 documented; ≤2 recommended for prototype) |
| Forbidden | implementation, measurement, threshold pre-registration |
| Merge gate | doc exists; covers normalised W2 ratio / entropy-OT / JS-trajectory / Fisher-Rao / spectral; per-candidate invariance property + assumptions + controls + failure mode |

### PR M2.5 — M2 Pre-registration (Path A / Path B)

| field | value |
|---|---|
| Adds | `contracts/M2_BRIDGE_EXPERIMENT_PRE_REGISTRATION.yaml`, `tests/test_m2_bridge_contract.py` |
| Modifies | nothing executable |
| Asserts | two mutually exclusive experiment paths fully specified; thresholds, seeds, nulls, verdicts, forbidden post-hoc actions, contract hash binding, reproduction command |
| Forbidden | substrate measurement, prototype code, threshold relaxation |
| Merge gate | contract parses; both paths exist; both list PASS / FAIL_OFFBAND / FAIL_NULL_LEAK / INVALID_OPERATOR / INVALID_PRECONDITION; no `TBD` thresholds; no contracted measurement output yet; tests pass |

### PR M2.6 — Prototype One Path (controls only)

| field | value |
|---|---|
| Adds | implementation of either spatial embedding or scale-invariant operator + positive control + negative control |
| Modifies | NOT the registry (`current_status` stays `OPEN_NARROWED`) |
| Asserts | controls pass; operator passes pre-registered scale check on synthetic data |
| Forbidden | substrate measurement, threshold mutation, claim flip |
| Merge gate | controls pass deterministically; CI green; lint passes; M2.2 scale diagnostic re-run on the new operator |

### PR M2.7 — Contracted Measurement

| field | value |
|---|---|
| Adds | `results/m2_bridge/run_v1.json` (or path declared by M2.5 contract) + invocation script |
| Modifies | `contracts/M_BRIDGE_CLAIM_STATUS.yaml` to record the verdict |
| Asserts | the verdict produced by the contract — PASS, FAIL_OFFBAND, FAIL_NULL_LEAK, INVALID_OPERATOR, or INVALID_PRECONDITION |
| Forbidden | any reinterpretation, threshold widening, or seed dropping |
| Merge gate | contract sha256 binds the JSON; reproduction command works; verdict accepted as-is |

## Dependency graph

```
M2.1 (this PR)
   └── M2.2  (scale diagnostics)
         ├── M2.3  (spatial embedding design)
         └── M2.4  (operator candidates design)
                ├──── M2.5  (pre-registration, picks one path)
                            └── M2.6  (prototype + controls)
                                  └── M2.7  (contracted measurement)
```

`M2.3` and `M2.4` may proceed in parallel after `M2.2` lands. `M2.5`
must wait for both to merge so that the chosen path can reference the
recommended embedding/operator. `M2.6` and `M2.7` are gated on `M2.5`.

## Forbidden shortcuts

The following are forbidden across all M2 PRs, enforced by reviewer
discipline plus the lint tool added in this PR:

- merging measurement and design in the same PR
- promoting `current_status` from `OPEN_NARROWED` without a passing
  contracted measurement
- treating M2.2 synthetic results as evidence about substrates
- using the M2.6 prototype's positive control as substrate evidence
- amending a contract YAML in the same PR that records the result
  produced by that contract

## Expected artifacts after the full split lands

- `docs/reports/M_INVARIANT_BRIDGE_STATUS.md` — current verdict + forbidden reinterpretations
- `contracts/M_BRIDGE_CLAIM_STATUS.yaml` — machine registry
- `tools/audit/m_bridge_claim_lint.py` — claim drift gate
- `experiments/m_invariant_scale_diagnostics/` — synthetic harness
- `docs/design/BNSYN_SPATIAL_EMBEDDING_FOR_HWI.md`
- `docs/design/SCALE_INVARIANT_BRIDGE_OPERATORS.md`
- `contracts/M2_BRIDGE_EXPERIMENT_PRE_REGISTRATION.yaml`
- (post-M2.7) `results/m2_bridge/run_v1.json` + a verdict in the registry

## What this roadmap is and is not

- It IS a contract for how the next series of PRs will be sized and gated.
- It IS the place to update if the dependency graph changes.
- It is NOT a scientific claim; nothing here asserts a bridge.
- It is NOT a place to record verdicts; verdicts live in the registry
  and are written only by M2.7.
