# ⊛ H4 — Training a Value Predictor Without Confusing it with Temporal-Difference Learning

**Status:** implemented, executed offline (23/23 targeted tests PASS), eight synthetic seeded runs archived as a summary.  
**Scientific verdict:** `SYNTHETIC_ONLY_REAL_DNCA_TD_UNTESTED`.  
**Branch scope:** instrument development, NOT DNCA cognitive-benefit proof.

## 1. First-principles separation

Two signals exist at different points in causal time.

Before checking claim `i`, an agent may form an estimate
`V_theta(s_i)=E[r_i | s_i, D_train]`. This is an **ex-ante prediction**.
An independently established reward `r_i` becomes available **after**
verification. Only then can an innovation/residual be calculated.

For a terminal event `delta_i = r_i - V_theta(s_i)`; in a
**nonterminal Markov trajectory**, a standard TD error is
`delta_t = r_t + gamma V_theta(s_{t+1}) - V_theta(s_t)`.

`delta_i` or `delta_t` cannot be used for the SAME claim's selection
when its `r_i` has not been observed. Such an operation would use
oracle information to select the claim allegedly being tested.

**Implementation decision:** H4 studies **supervised value prediction** and
held-out allocation. It does NOT claim that DNCA's real
`DopamineOperator` performed trained temporal-difference learning, or that
a terminal residual with discount 0 equals the DNCA's current
`gamma=0.99` implementation.

## 2. What was really trained and compared

Executable: `experiments/dopa_signal_validity/trained_value_falsification.py`.

The small PyTorch network uses the exact layer family and relative shape of
`DopamineOperator.value_net`:
`Linear(d, hidden//2) -> GELU -> Linear(hidden//2,1)`.
It is a separate experimental instance; **not** the live DNCA operator.

The synthetic label generator uses
`logit(P(r=1|x)) = 0.40*x0 + 1.25*x1 - 1.10*x2 - 0.10`,
followed by Bernoulli sampling. This mechanism deliberately makes a
linear model correctly specified, a stringent falsification comparator.
Baseline observations with only `x0` have reduced information.

Each seed uses:
- 1,200 training examples and 320 validation examples from separate RNG
  streams; 384 held-out examples in 24 groups of 16.
- Exactly four ex-ante selections per group for **every policy**.
- A frozen value-net network with validation Brier early stopping,
  an identical **untrained** value network, a reward-shuffled network
  (both training and validation labels shuffled independently),
  a trained full-feature **linear** competitor, a trained single-feature
  linear baseline, and a ceiling calculated using held-out labels
  **only after selection**.
- Independent model checkpoints and dataset SHA-256 per seed.
- Brier score (proper probabilistic scoring) and useful selections per group.
- Per-arm observed train and inference wall time. These durations are
  **recorded**, not matched. Equal selection slots do NOT mean equal compute.

No held-out label enters model fitting, checkpoint selection or ranking.
Scoring and top-k indices are calculated **before** reading held-out rewards.
Only evaluation consults labels.

## 3. Actually executed results, 2026-10-16

Runtime: Python 3.13.5, PyTorch 2.10.0+cpu, NumPy, CPU.
Eight fixed seeds:
`731, 1031, 1331, 1631, 1931, 2231, 2531, 2831`.

| Policy | Mean Brier ↓ | Mean beneficial picks of 4 ↑ |
|---|---:|---:|
| Trained value network | **0.16993** | **3.34375** |
| Full-feature trained linear model | 0.17264 | 3.31771 |
| Untrained value network | 0.25251 | 1.94792 |
| One-feature linear model | 0.24673 | 2.16146 |
| Shuffled-reward network | 0.25124 | 1.93750 |

Paired neural-minus-full-linear selection gain: **+0.02604 picks per
four-slot group**, seed-level descriptive bootstrap 95% interval
**[-0.03646, +0.10417]**. This interval includes zero.

The predeclared **stronger baseline is competitive**. The observed tiny mean
difference does not establish a neural architectural advantage. The trained
model does outperform the untrained network by about **1.39583 picks per
four-slot group** on this purposely learnable synthetic task. This
demonstrates learning of a constructed feature–label relationship, not
emergent intelligence or the biological validity of neuromodulators.

Eight seeded repeats are not external replication; the same data-generating
mechanism is used each time. Bootstrap across only eight seeds is
**descriptive** and not a power analysis or a causal efficacy result.

## 4. Reproducibility and source identity

Four committed files were verified byte-for-byte against their executed
local copies:

| File | Git content blob SHA |
|---|---|
| `experiments/dopa_signal_validity/trained_value_falsification.py` | `213e16a02ba20aca8df13e8e6ef524c9345fae33` |
| `experiments/dopa_signal_validity/h4_replicate_study.py` | `5c2bb2a8f3436d0704ed03ccc0d938ab6fa4f0f6` |
| `tests/dopa_closure_v2/test_trained_value_falsification.py` | `9439862976202b3dfbd6aab570b749512ade3c05` |
| `tests/dopa_closure_v2/test_h4_replicate_study.py` | `890df014a185e0368764b0f5cd381a2d653565c8` |

After removing nondeterministic *timing fields* from the archived replay,
the detailed eight-seed JSON's pre-digest SHA-256 was:
`8e902328f7d3fcb9c79078234396469f947f0c9e75a4c6ce36e703cf4d920997`.

See `evidence/dopa_signal_instrument/H4_TRAINED_VALUE_EIGHT_SEED_SUMMARY_2026-10-16.json`
for aggregate metrics, source IDs and methodological caveats.

Standalone verified tests: **23/23 PASS**, including nonleakage,
model-versus-random divergence, identical checkpoint/metrics on replay,
input validation, source structure, hash integrity, negative-control
protocols and no-automatic-promotion. **Full monorepo CI, Ruff, Mypy
and actual DNCA.step integration have NOT been executed here.**

Reproduce from repository root with installed Python and PyTorch:

```bash
python -m pytest -q tests/dopa_closure_v2/test_trained_value_falsification.py \
  tests/dopa_closure_v2/test_h4_replicate_study.py
python -m experiments.dopa_signal_validity.trained_value_falsification \
  --output /tmp/h4_one_seed.json
python -m experiments.dopa_signal_validity.h4_replicate_study \
  --output /tmp/h4_eight_seeds.json
python scripts/verify_neuroai_offline.py
```

Files are created in **exclusive no-overwrite mode**, and SHA-256 here is a
content integrity check, not independently authenticated provenance.

## 5. Hard remaining gates — do not promote

**H5 is not optional.** A meaningful DNCA benefit claim requires:

1. **Independent oracle**: independently verified benefit or correctness,
   original claim commitments and authenticated evidence receipts.
2. **Correct temporal semantics**: train a genuine sequential
   `V_theta(s_t)` using temporally aligned rewards and nonterminal states,
   where appropriate; freeze the checkpoint and check how real
   `DNCA.step` propagates the **post-reward** signal.
3. **Strict information barrier**: only ex-ante information can choose
   which claim to verify. The RPE of a claim may update *future* policy,
   never retroactively choose the same claim.
4. **Strong null models**: direct uncertainty baseline, full-feature
   linear predictor, random and reward-shuffled networks,
   sign-reversed and within-group permuted signals.
5. **End-to-end resources**: include data preparation, DNCA initialization,
   training, inference, actual verifier execution, retries and token/CPU/GPU
   utilization. Policy slot matching is inadequate.
6. **Held-out paired comparisons**: predeclare practical minimum improvement,
   uncertainty estimates, false-closure upper bounds, adverse-case tests,
   and independent cross-host reproduction.

**⊛ Quintessence:** a trained predictor can be useful without being a
dopamine-like TD learner; a complex model may learn without outperforming
a simpler correctly specified baseline. The evidence must select the
architecture, not the architecture select the evidence.
