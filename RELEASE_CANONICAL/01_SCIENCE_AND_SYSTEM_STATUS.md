# Scientific SSOT — DNCA/DOPA H1–H5

**Status at 2026-10-17:** research R&D prototype. Real-world/general intelligence superiority **NOT established**. This release preserves every previously tracked evidence file and retraction at the frozen parent commit.

| Stage | Actual implementation | Evidence-constrained conclusion |
|---|---|---|
| H1 / PR #5–12 | DNCA → DOPA routing, independent arithmetic verification, provenance, budget, fail-closed offline gate | Routing priority does not itself establish factual correctness. Full CI still unverified. |
| H2 / PR #13 | Synthetic cue calibration with null, shuffled, sign-reversed controls | Experimental instrument detects **artificially injected information**; not DNCA efficacy. |
| H3 / PR #14–16 | Global valence no-go; claimwise analysis; first-step TD audit | A common shift cannot invert fixed-base order. One-step zero-reward `valence` probes untrained value-net, not learned RPE. |
| H4 / PR #17 | Supervised V(s) with held-out synthetic rewards, full-feature linear baseline | Learning exceeds random initialization; unique advantage over correct strong linear baseline is unproved. |
| H5 / PR #18 | Forward-view TD(λ) on executed stochastic **software** environment trajectories; process-separated oracle; frozen value_net checkpoint adapter | Neural holdout return-MSE lower on tested seeds, but model is much larger and full resource parity absent; this is not field or global DNCA proof. |

## The most important H5 facts

At `main@04f232e22066e594a29fa9b95e28a7ac48851122`:

- Training has `TD(λ)` episode replay using frozen next-state predictions, with discount `γ=0.95` and trace coefficient `λ=0.8`.
- The control compares a neural network (161 weights, ~144 dense MACs/state) against full-state linear prediction (9 weights, ~8 MACs/state).
- Eight simulator seeds report approximate mean holdout return-MSE of **0.62137 neural** and **0.70724 linear**. This is *not* an equal-total-compute causal advantage.
- H5 local targeted tests reported **23/23 PASS**, and the seed-19 evidence JSON is preserved at `evidence/dopa_signal_instrument/H5_SOFTWARE_ENV_SEED19_2026-10-16.json`.
- New `DopamineOperator.install_frozen_value_weights` validates tensor state_dict SHA-256 and dimensions. New `predict_value_ex_ante` reads a frozen prediction without current reward.
- Original DNCA full-runtime integration tests are committed but **not reported as executed**. Production readiness and GitHub Actions full gate PASS are **UNVERIFIED**.
- The separate-process reward oracle shares the simulator's software trust domain; it does not independently authenticate environmental reality.

## Governing paths

- `docs/research/DNCA_H5_TDLAMBDA_SOFTWARE_ENV_PROTOCOL_2026-10-17.md`
- `docs/research/DNCA_H4_TRAINED_VALUE_FALSIFICATION_2026-10-16.md`
- `docs/research/DNCA_FIRST_STEP_TD_CONSTRUCT_CORRECTION.md`
- `docs/research/DNCA_VALENCE_GLOBAL_SHIFT_NO_GO_2026-10-16.md`
- `docs/research/DNCA_DOPA_SCIENTIFIC_EVIDENCE_CASE.md`
- `evidence/dopa_closure/RETRACTION.md`
- `scripts/verify_neuroai_offline.py`

## Mandatory semantic invariants

```text
local test PASS != complete repository CI PASS
source merge != executed integration test
synthetic environment != authenticated real-world trajectories
oracle subprocess != independently trusted truth authority
prediction loss improvement != causal policy improvement
causal improvement != general DNCA effectiveness
Git blob integrity != signatory scientific provenance
```

The previous invalid falsification proxy was retracted. Do not silently restore any academic conclusion that prior evidence retracted. Follow actual source code, preregistered estimands, independent evidence, and negative controls.
