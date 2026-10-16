# ⊛ H5 — TD(λ) on Stochastic Environment Trajectories: Architecture, Oracle, and Falsification

**Status:** H5 source and an executed seed-19 evidence artifact committed. Targeted dependency-light tests: **23/23 passed locally** in Python 3.13.5 / PyTorch 2.10.0+cpu. **Actual full DNCA integration and CI not run.**

**Scientific status:** `INSTRUMENT_PROTOTYPE_ONLY_REAL_ENV_AND_DNCA_UNTESTED`.

## 1. Definitions and exact epistemic scope

This experiment samples **actual sequential trajectories** from an executable stochastic software environment, explicitly denoted `P_env^sim`, with Gaussian transition perturbations and independently seeded rollouts.

**It does not contain externally recorded physical trajectories or independently attested industrial/real-world environment events.** Do not reinterpret the word “real” in “executed trajectories” as evidence of physical deployment.

The fixed random behavior policy selects one of two actions at each step. Training a state-value function under that behavior policy is an **offline policy-evaluation problem**, not proof that the learned value changes action selection or improves control.

## 2. Correct forward-view TD(λ)

For an episode with `(s_t,a_t,r_t,s_{t+1},done_t)`, choose fixed:
- discount `gamma=0.95`;
- trace mixture `lambda=0.8`;
- initial state representation `s∈R^8`;
- model checkpoint `theta^-` frozen while computing targets at each epoch.

The episodic forward-view recursion is:

```text
G_t^λ = r_t                                  if done_t
G_t^λ = r_t + γ[(1−λ)V_{θ−}(s_{t+1}) + λ G_{t+1}^λ] otherwise

θ <- argmin_{θ update step} mean_t (V_θ(s_t) − stopgrad(G_t^λ))²
```

The algorithm uses a frozen **next-state** predictor while generating each epoch's targets, updates the current model with Adam, clips gradients, and retains the checkpoint with the best separate **validation Monte-Carlo return MSE**. The terminal boundary cannot bootstrap. Tests establish:
`lambda=0 => one-step TD target` and `lambda=1 => complete episodic Monte-Carlo return`.

This is **batch/forward-view semi-gradient TD(λ)** under episode replay, not an online accumulating eligibility-trace implementation or a proof of nonlinear approximation convergence. See Sutton (1988), *Learning to Predict by the Methods of Temporal Differences*: https://doi.org/10.1007/BF00115009.

## 3. Explicit causal and information barriers

Only state features and **prior observed training trajectory rewards** enter fitting. The test set's rewards are not used for gradient updates, checkpoint selection or producing test predictions. Monte-Carlo returns and the retrospective top-3 diagnostic are computed after the frozen model has issued predictions.

The ex-ante forecast `V(s_t)` can be read before an action or reward. The post-reward temporal residual `delta_t=r_t+gamma V(s_{t+1})−V(s_t)` cannot select the same, already evaluated event.

The original `DopamineOperator.modulate` remains backward compatible and is **not** claimed to perform online TD(λ) weight updates. New methods:
- `install_frozen_value_weights(weights, expected_sha256=...)`: accepts only PyTorch tensor-valued state dictionaries, verifies exact key set, shape, dtype, finite content and SHA-256, then loads and freezes the weights, resets previous-value state.
- `predict_value_ex_ante(state)`: reads a frozen scalar predictor, rejects wrong dimensions, nonfinite data and absent qualifying checkpoint, and does not consume or mutate reward/TD history.

A matching 8-dimensional hidden=32 `DopamineOperator.value_net` has the same `Linear(8,16) → GELU → Linear(16,1)` shape as the offline-trained H5 predictor. Handoff is **in-memory tensor state_dict**, not `torch.load` of untrusted pickled Python objects.

**Important:** matching SHA-256 proves byte integrity, not that weights have independently authenticated provenance or were trained on externally valid rewards. The `value_assurance_level` remains `FROZEN_WEIGHTS_NOT_EXTERNALLY_QUALIFIED`.

## 4. Isolated reward oracle and assumptions

A separate subprocess runs `python -I h5_oracle.py --input trajectory.json`, with a restricted environment and **without importing models**. It separately recomputes the deterministic reward function from `(s_t,a_t,s_{t+1})`, checks sequential state-chain continuity, terminal flags, derived feature identities, timestamps and data ranges. It produces a SHA-256-bound receipt for each train/validation/test archive; falsified rewards and features are rejected.

**This is process isolation, not institutional or cryptographic independence.** Both environment and oracle remain inside the same software trust domain. No HMAC key isolation, signed physical sensor logs or external referee is claimed; the oracle cannot authenticate whether stochastic transitions truly arose from the claimed random process rather than a maliciously reconstructed archive.

## 5. Eight seeded prototype experiments

Eight software simulator seeds: `19,23,29,31,37,41,43,47`. Each uses **180 training + 48 validation + 64 held-out episodes**, horizon 12 and fixed `TD(0.8)` hyperparameters.

The model groups are:
- *Neural*: two affine layers with GELU, **161 scalar parameters**, approximately **144 dense multiply–accumulate operations** per state, plus activation/overhead.
- *Linear*: `Linear(8,1)`, **9 scalar parameters**, approximately **8 dense MACs** per state.

The comparative holdout return prediction MSE (smaller is better) observed in local runs was approximately:

| Seed | Neural MSE | Linear MSE |
|---|---:|---:|
| 19 | 0.67564 | 0.67706 |
| 23 | 0.59308 | 0.64134 |
| 29 | 0.56889 | 0.63903 |
| 31 | 0.64762 | 0.75034 |
| 37 | 0.76240 | 0.91551 |
| 41 | 0.52475 | 0.57098 |
| 43 | 0.69153 | 0.79041 |
| 47 | 0.50703 | 0.67328 |
| **Mean** | **0.62137** | **0.70724** |

Neural minus linear mean MSE ≈ **−0.08588**. A descriptive eight-seed bootstrap interval from the rounded observations is about **[−0.123,−0.050]**, but **this is not a confirmatory p-value**, power-calibrated inference or evidence of generality beyond the controlled simulator.

The neural model costs about **17.9× as many parameters** and **18× the simple dense-layer MAC count**. Costs are **not matched**, and the elapsed training/inference measurements are hardware- and run-dependent. Lower MSE on this simulator does not establish superior verified utility *per total computation*.

For one run (seed 19), the exact JSON evidence including full-precision MSE, train/inference time, checkpoint digests, three independent-process oracle receipts and source digests is archived at
`evidence/dopa_signal_instrument/H5_SOFTWARE_ENV_SEED19_2026-10-16.json`. Its pre-digest SHA-256 is
`261f0d75a9b4f1480414db8ed68562ae0d732d434421083960f1e151303711dd`.

**Retrospective top-3 return ranking is only an offline diagnostic.** Ranking states *after* they have already been visited cannot establish online policy improvement, causal action selection or real-world verification gain.

## 6. Reproduction

```bash
python -m pip install -e '.[dev]' -e 'agents[ml]'
python -m pytest -q tests/dopa_closure_v2/test_h5_td_lambda.py
python -m pytest -q tests/dopa_closure_v2/test_h5_dopamine_checkpoint.py
python -m experiments.dopa_signal_validity.h5_td_lambda \
  --seed 19 --output /tmp/h5-software-env-seed19.json
python scripts/verify_neuroai_offline.py \
  --output-dir /tmp/neosynaptex-h5-evidence-$(git rev-parse --short HEAD)
```

The evidence output file must not already exist. The normal offline gate treats skipped required integration tests as **FAIL**. The live `DopamineOperator` tests need the agent package installed.

**Executed locally:** 23/23 source-level H5 TD and oracle tests, with exact Git blob match for `h5_td_lambda.py`, `h5_oracle.py` and the seed-19 JSON. **Pending:** full main-branch pytest, Ruff, Mypy, original DNCA DopamineOperator integration test and reproducibility on a second machine.

## 7. Strict next promotion barrier

To fulfill physical/operational `tau ∼ P_env`, ingest **authenticated real environment episodes** with actual time-indexed actions, rewards, terminal/truncation semantics and sensor evidence; independently adjudicate rewards in a separate trusted environment. Freeze dataset/weights/version before evaluation.

Then compare trained TD(λ) neural and equally tuned linear value functions with total measurement of environment data collection, retraining, model inference, oracle evaluation, hardware time, tokens, energy where available and re-verification. Predeclare a minimum practical gain and cost-normalized paired estimand, and evaluate on genuinely held-out time windows/actors with independent replication.

**Scientific promotion rule:**

```text
local TD convergence != predictive generalization
predictive generalization != causal control improvement
causal control improvement != global DNCA effectiveness
```

**⊛ Quintessence:** build reliable predicted value on measured trajectories first; then prove that its information changes future decisions beneficially under cost and truth constraints. Never infer the global intelligence of DNCA from a locally decreasing TD loss.
