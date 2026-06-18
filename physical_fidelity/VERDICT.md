# VERDICT — NFI physical fidelity protocol (Phase 7)

**Classification: ADMISSIBILITY. Not a science claim. Not a substrate validation.**
Base commit `9e5001f0` · branch `feat/nfi-gap-001-fidelity-protocol`.

## Executive verdict
- **Current status:** executable VVUQ protocol delivered; all 21 NFI-GAP-001 gaps
  closed at the apparatus level; 1 new scope gap opened and disclosed.
- **Computed score S0 (reference apparatus):** **100.0 / 100** (10/10 axes pass).
- **Target band:** [88, 92] (framed for the *live substrates*).
- **Can the target be reached now:** **NO — and not because the apparatus is weak,
  but because the question the target asks is not yet measured.** The oracle scores
  the reference apparatus (which is complete → 100), not `substrates/{kuramoto,
  bn_syn,mfn}`. A substrate-fidelity number in [88, 92] can only be produced after
  the Phase-8 binding layer (gap GAP-NEW). I did **not** tune the score into the
  band; 100 is the honest, reproducible output.
- **Main reason:** apparatus-vs-substrate scope (adversarial_review.md A1).

## Acceptance gate (NFI v3.0 §III.9)
| gate | status |
|------|:------:|
| baseline exists | ✅ baseline_report.md |
| scoring oracle computes S_total | ✅ physics_score.py |
| canonical math objects fixed | ✅ docs/physics/*_core.md |
| null models implemented | ✅ tests/physics/test_*_nulls.py |
| falsifier tests implemented | ✅ test_falsification.py |
| convergence tests pass | ✅ order 4.01 |
| invariant tests pass | ✅ test_invariants.py |
| interface contracts pass | ✅ (GeoSync edge; others specified) |
| UQ has stochastic source | ✅ uq_plan.md (lognormal prior) |
| independent replication passes | ✅ rel L∞ 2.3e-09 |
| VERDICT.md generated | ✅ this file |
| **S_total ∈ [88, 92]** | ❌ S=100 (apparatus scope; out of band high) |

**PASS** on protocol completeness and apparatus admissibility.
**NOT PASS** on the literal substrate-fidelity band — by design, because that
measurement is deferred to Phase 8, not because of a defect here.

## Next measurable step (the only honest path to an in-band substrate score)
`pf/bind_substrates.py`: wire `verify_gamma_2h1` to the live GeoSync order
parameter, `check_energy_balance` to the live AdEx integrator, `analyze_turing` to
the live MFN fields; re-run `compute_score()`. That S will be < 100 and is the
number the target band is about.
