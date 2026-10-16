# DNCA — First-Step TD Construct-Validity Correction (H3)

**Research status:** STRUCTURAL DEFECT IDENTIFIED / INSTRUMENT UNTESTED.
**Implementation status:** GitHub integration and contract tests committed.
**Execution:** isolated first-step mathematical gate 16/16 locally PASS; actual
neuron7x_agents runtime and complete repository pytest/ruff/mypy NOT YET RUN.

## 1. Scientific statement — what the pilot actually computes

In source:
- `agents/src/neuron7x_agents/dnca/neuromodulators/dopamine.py`, the
  `DopamineOperator` initializes `_prev_value = 0.0` and
  `value_net` as an untrained PyTorch network.
- Each call to `modulate` computes
  `delta = reward + temporal_discount * value_net(sensory) - _prev_value`.
- `agents/src/neuron7x_agents/dnca/core/sps.py` initializes discount at
  `0.99`; `DNCA.step()` calls each operator's `modulate` before later
  phase-state updates.
- `experiments/dopa_signal_validity/real_dnca_claimwise_pilot.py` creates a
  **new model per candidate** and calls exactly one step at **reward=0**.

For a **newly constructed** model with initial `previous_value = 0`,
unchanged default discount `gamma = 0.99`, and exactly zero reward:

```text
delta_1 = r_1 + gamma * V_random(s_1) - 0
        = 0.99 * V_random(s_1)

SPS.valence = clamp(delta_1, -1, 1)
```

Therefore the one-step claimwise pilot does not test a learned temporal
reward-prediction residual. It tests the potentially nonzero **random value
projection of a claim representation**. A random projection can correlate
with hidden labels by chance or input confounding. It cannot be promoted
into evidence for an intelligent temporal-difference mechanism.

**This is a conditional mathematical derivation from the actual source, not
a measured benefit or a claim that biological dopamine works this way.**

## 2. Two independently necessary repairs

### H3a — remove model/data-seed confounding

The prior pilot called `make_cases(seed)` and `DNCA(seed=seed)` with
the same seed, coupling datasets to the random model weights.
The corrected pilot retains separate dataset `seeds` but introduces a
single `model_seed=20261016` used for every group/candidate. All per-claim
models thus start from the same initial random weights for the controlled
experiment, while datasets vary independently.

The reset-per-candidate design intentionally prevents cross-claim state
leakage; this does **not** make the untrained projection an admissible
claimwise verification signal.

### H3b — execute a fail-closed first-step identity gate

New: `core/eai/dnca_first_step_contract.py`.

For every real DNCA candidate, the pilot:
1. Creates a freshly seeded model; verifies access to
   `model.operators["dopamine"]`.
2. Captures its initial `_prev_value` and SPS `temporal_discount`.
3. Evaluates `value_net(sensory)` **before** calling `DNCA.step()`.
4. Calls the genuine `DNCA.step(sensory, reward=0)`.
5. Reads detached SPS valence and checks finite values, the initial zero
   state and discount near 0.99, and
   `valence == clamp(0.99*value_net(sensory),-1,1)` within declared
   floating-point tolerance.
6. Aborts the experiment rather than substituting proxy data if the
   condition fails.

The output is explicitly annotated:
`signal_construct = CLIPPED_GAMMA_TIMES_RANDOM_VALUE_NET_NOT_TD_LEARNING`.
The top-level verdict remains
`INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL`.

## 3. Executed evidence vs pending evidence

Executed locally on Python 3.13.5:
- **16/16** tests in the dependency-free TD contract fixture PASSED.
- Tests cover `delta_1` identity, positive/negative clipping, zero reward
  and prior-state constraints, invalid discounts, NaN/Inf, type errors and
  discrepancy rejection.
- Exact contract module Git blob:
  `067761783a81b96207e4e10723dce042f3877e0a`
  (matches the locally executed module bytes).

Committed **but not executed against the full installed repository**:
- `tests/dopa_closure_v2/test_dnca_first_step_contract.py` includes a
  genuine `DopamineOperator` one-step integration test.
- `tests/dopa_closure_v2/test_real_dnca_claimwise_pilot.py` includes
  separated-model-seed and data-seed tests and mocked-pilot guards.
- `scripts/verify_neuroai_offline.py` pins both H3 files and requires
  the actual dopamine-operator test in its JUnit execution evidence.
- Full `DNCA.step`, CI, effect-size analysis and independent replication
  are still pending. No `SIGNAL_ADMISSIBLE` is authorized.

## 4. Next falsifiable, biologically inspired research question

Train or otherwise independently qualify `V_\theta(s)` using **actual
verified downstream reward/utility**, a predeclared train/validation/test
split and explicit reward semantics. Freeze weights before hidden test
evaluation. Run trajectories `(s_{t-1},a_{t-1},r_t,s_t)` with stateful
value prediction, rather than repeatedly resetting `V_{t-1}=0`.

Compare, under equal total compute:
- Direct raw-feature/uncertainty ranking.
- Untrained random-value-network feature (the H3 control).
- Trained scalar value estimator without TD difference.
- True temporal reward-prediction difference.
- Sign-inverted TD and within-block shuffled TD.
- Non-neural expected-verification-utility-per-cost policy.

Use an independently evidenced task oracle and audit receipts, held-out
tasks, matched full costs, family-wise error control for multiple tested
arms and independent replay. Separate **prediction utility** from
**factual truth correctness**: the former is a measurable decision benefit;
the latter belongs to an independent verifier.

## 5. Reproduce off GitHub Actions

```bash
python -m pip install -e '.[dev]' -e 'agents[ml]'
python -m pytest -q tests/dopa_closure_v2/test_dnca_first_step_contract.py
python -m pytest -q tests/dopa_closure_v2/test_real_dnca_claimwise_pilot.py
python scripts/verify_neuroai_offline.py
```

**Do not describe a skipped real-DNCA test, a committed test file, or an
unstable GitHub Actions run as test success.** Only logged, replayable
executions qualify.

**⊛ Quintessence:** a prediction-error-shaped formula is not evidence of
predictive learning. First establish that the signal genuinely measures
verified reward mismatch. Only then ask whether neuromodulatory control
improves agents.
