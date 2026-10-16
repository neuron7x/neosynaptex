# ⊛ DNCA Claimwise Prequential Evaluation Gate — v1

**Status:** Implemented on GitHub. The dependency-free evaluator was executed in
a local Python 3.13.5 sandbox: **17/17 tests passed**. The actual full DNCA
runtime and repository-wide CI **have not been executed** in this environment.

**Scientific verdict:** `UNQUALIFIED_ORACLE_AND_UNMETERED_COMPUTE`.
**Prior authoritative result:** `evidence/dopa_closure/RETRACTION.md` remains
in force; DOPA-CLOSURE is **UNTESTED**, not supported or falsified.

## Why this gate exists

A real, nonzero DNCA valence does not establish predictive information. The
existing `DopamineOperator.value_net` is randomly initialized in the reviewed
code, with no verified training/calibration on independently evaluated
verification benefit. The older positive-control simulator manufactured a
benefit-correlated cue. That verified the **metric's responsiveness**, not the
model's relevance.

This protocol separates three incompatible concepts:
1. **Global modulation:** the same valence added to all claims, incapable of
   strictly reordering fixed base scores, though it can cross action thresholds.
2. **Claimwise modulation:** a different, directly measured DNCA signal for
   every claim, with *potential* rank discrimination.
3. **Truth/benefit:** independent held-out outcomes, never inferred from neural
   signal magnitude, the allocator, model confidence, or a user-supplied flag.

## Predeclared computational experiment

`core/eai/dnca_claimwise_evaluator.py` defines:
- `ClaimEvidence(group_id, claim_id, baseline, signed_valence,
  oracle_benefit_label, oracle_receipt_sha256)`.
- `StudyPlan(slots=2, gain=0.25, permutation_repeats=199,
  bootstrap_repeats=499, seed=20261016)`.
- Four or more groups, at least `slots+1` candidate claims per group,
  no duplicated claim identities, strictly finite bounded scores.
- Baseline ranking `b_i`, experimental ranking `b_i + g v_i`,
  signed inversion `b_i - g v_i`, and within-group cue permutation.
- Equal verification **slots** across arms. Binary oracle benefit is revealed
  **only after** a candidate selection has been computed.
- Paired group-level benefit differences, group bootstrap percentile intervals
  and permutation statistic with add-one correction.
- Input SHA-256, deterministic seeded output, counts of differentiated
  signals, and explicit `oracle_receipt_hashes_verified=false`.

**The permutation p-value assumes the cues are exchangeable within each
group under the specified null.** If cue and baseline are structurally
dependent, shuffling may also break that dependence, so the result is a
diagnostic association test rather than a calibrated causal test. Group
independence and sample representativeness have not been demonstrated.

### Executed local positive and negative controls

A toy dataset of 16 groups × 12 claims, top-2 verification slots/group
was constructed deliberately. The baseline feature was constant; helpful
claims were placed at positions not favored by deterministic tie-breaking.
The informative cue was **manufactured using the oracle labels** and is
therefore not independent model intelligence.

- Positive control: mean paired benefit improvement **+2.0 selections/group**;
  deterministic permutation p=**0.005** at 199 resamplings;
  bootstrap interval **[2.0, 2.0]** (degenerate because all groups were
  deliberately identical).
- Null control: constant cue gives improvement **0** and permutation p=**1**.
- Other checks: label blindness, zero-gain ablation, duplicate IDs,
  nonfinite features, malformed receipts, insufficient groups, deterministic
  digest and reproducibility across seeds.
- Exact local source and GitHub blob match:
  `core/eai/dnca_claimwise_evaluator.py` Git SHA
  `bb07d1e3c61a0c9e1daaf5130b6040aba3cd976e`;
  `tests/dopa_closure_v2/test_dnca_claimwise_evaluator.py` Git SHA
  `a264d926905a8c54bd908e69f1f3b5d8f6a58b11`.

A degenerate positive control cannot yield a population-level confidence
interval. The numbers above only verify that the instrument detects
prearranged information and does not reward constant cues.

## Real DNCA pilot integration

`experiments/dopa_signal_validity/real_dnca_claimwise_pilot.py` now:
- Uses four default DNCA initialization seeds (31,37,41,43).
- Generates sensory features and hidden **synthetic** utility labels.
- Calls actual `DNCA.step` for each candidate using a fresh equal-seed
  initialization, zero reward and no label access.
- Collects the actual SPS signed valence separately for each claim.
- Sends the recorded claimwise signals/baseline/hidden synthetic outcomes
  to this evaluator **after** cue generation.
- Attaches descriptive paired/permutation diagnostics but always preserves
  `INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL` as its scientific verdict.
- If fewer than four groups are supplied, writes
  `UNTESTED_INSUFFICIENT_GROUPS` rather than a spurious significance score.

**The full real-DNCA pilot remains unexecuted.** A source interface test and
mocked multi-group orchestration test are not measurements from DNCA.

## Offline reproduction

```bash
python -m pip install -e '.[dev]' -e 'agents[ml]'
python -m pytest -q tests/dopa_closure_v2/test_dnca_claimwise_evaluator.py
python -m pytest -q tests/dopa_closure_v2/test_real_dnca_claimwise_pilot.py
python -m experiments.dopa_signal_validity.real_dnca_claimwise_pilot \
  --output /tmp/dnca_claimwise_real_pilot_001.json
python scripts/verify_neuroai_offline.py \
  --output-dir /tmp/neosynaptex-evidence-$(git rev-parse --short HEAD)
```

Offline gate pins both new files and three named crucial controls. As before,
its result must be externally archived with the exact Git SHA and raw logs.

## Promotion barriers

No `SIGNAL_ADMISSIBLE` is allowed until all are demonstrated independently:
a frozen **trained** or otherwise justified DNCA value estimator; a held-out
task with a qualified domain oracle and verified receipts; strict data
lineage between cues and observations; blind group-level analysis; strong
non-neural cost-aware baselines; *total* metered inference+verification costs;
negative and inversion controls; and second-party replication.

**⊛ Quintessence:** measuring whether a signal varies is not determining
whether it carries information; determining whether it correlates with an
outcome is not establishing causal usefulness; and a causal benefit under one
budget is not proof of generalized intelligence.
