# DNCA Global Valence — Identifiability No-Go and Claimwise Pilot

**Status:** structural result + reproducible mathematical regression tests;
real-DNCA claimwise *pilot implemented, NOT executed or qualified*.
**Scientific claim:** **DOPA-CLOSURE remains UNTESTED**, per
`evidence/dopa_closure/RETRACTION.md`.

## 1. Scope: two different control problems

The merged `core/eai/dnca_modulated_router.py::route_observation` applies a
**single** `DNCAObservation.signed_valence` to every claim:

```python
priority = max(0.0, base + dopamine_gain * observation.signed_valence)
```

This can change global action thresholds, inhibition holds and sequential
budget withdrawals. It is **not** evidence of which individual claim should
be preferred. The earlier synthetic instrument
`experiments/dopa_signal_validity/paired_instrument.py` injected a
*separate* cue for each candidate; it therefore tested a strictly more
expressive mechanism than the current global DNCA router.

## 2. Fixed-base ordering theorem (conditional)

Define:
- `i, j`: two claims.
- `b_i, b_j ∈ [0, ∞)`: baseline priorities evaluated at an **identical,
  fixed** remaining-budget ratio, with all other inputs held fixed.
- `v ∈ [-1,1]`: one globally shared DNCA signed valence.
- `g ∈ [0,0.25]`: finite nonnegative gain.
- `T(x)=max(0,x)`: nondecreasing clipping map.
- `q_i=T(b_i+gv)`: modulated priority.

If `b_i > b_j`, then `b_i+gv > b_j+gv`. Since `T` is
nondecreasing, `q_i >= q_j`. Therefore `q_i < q_j` is impossible:
**no strict pairwise rank inversion can result from a common scalar shift**.
Negative shifts can collapse smaller priorities into ties; different stable
tie-breaking policies can change a top-k *selection*, despite no strict rank
inversion.

**Boundary of theorem:** The existing allocator recomputes `b_i`
sequentially using its **remaining** budget. If earlier route actions spend
different budgets because `g` moves priorities across thresholds, later
`b_i` may differ between experiment arms. Thus the fixed-base proof does
not show that whole-run decisions or allocations are invariant. It shows
that such differences are explainable by global threshold/cost mechanics,
**not** per-claim signal discrimination.

Similarly, high global inhibition can quarantine all claims without
selectively identifying any particular claim.

## 3. Identifiability requirement for claimwise intelligence

To support claim-specific selective verification, define separately for
each claim `i` an observed `v_i` that is:
(1) obtained from a declared, audited inference path;
(2) independent of the hidden claim outcome/answer when computed;
(3) measured at a frozen model checkpoint under a declared time/compute
budget; and (4) independently validated for incremental benefit beyond
a strong matched-cost non-neural baseline.

Then `q_i=T(b_i+g v_i)` *can* reorder claims. But expressive capacity
is not predictive validity. A different `v_i` can be **pure noise**.

The existing DNCA `DopamineOperator.value_net` initializes random weights;
neither its signed valence nor RPE is demonstrated to predict actual
verification utility. No gain tuning can repair that construct invalidity.
Moreover `g=0` removes the signed-valence addition but leaves DNCA-derived
shared prediction-error magnitude inside every ClaimSignal's baseline;
**gain-zero is not equivalent to removing all neural inputs**.

## 4. Implemented pilot: real model, no oracle leakage

`experiments/dopa_signal_validity/real_dnca_claimwise_pilot.py`
contains an explicitly scoped future executable:

- Generate a synthetic, deterministic sensory feature set and a **separate**
  hidden benefit label vector; baseline scores depend only on features.
- For every candidate instantiate a **fresh** DNCA with the same seed,
  state dimension, initialization and no per-claim reward (`reward=0`).
  Take one real `DNCA.step`, read the actual SPS signed valence through
  `observe_sps`, and record initialization + forward wall-clock nanoseconds.
- Keep withheld outcomes outside the cue-generating function signature.
  Reset by fresh construction so prior candidate history and online learning
  cannot contaminate individual signals.
- Compare fixed-slot policies: baseline, actual claimwise valence, shuffled
  cue, reversed cue and the common-global-mean shift. Assess synthetic
  binary benefit *after* selection.
- Emit `INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL` regardless of observed
  improvement. Absence of PyTorch/DNCA is a hard error, never a random
  placeholder signal.

`torch`, `DNCA` and `value_net` are real dependencies. The current
pilot uses a synthetic outcome rule and randomly initialized DNCA and is
**not an external truthfulness benchmark**. Its score is not the number
of independently verified factual closures, and wall time is not complete
energy/token/runtime resource metering.

**Run only on a clean research checkout with GPU/CPU resources available:**

```bash
python -m pip install -e '.[dev]' -e 'agents[ml]'
python -m pytest -q tests/dopa_closure_v2/test_dnca_signal_identifiability.py
python -m pytest -q tests/dopa_closure_v2/test_real_dnca_claimwise_pilot.py
python -m experiments.dopa_signal_validity.real_dnca_claimwise_pilot \
  --output /tmp/dnca-real-claimwise-untrained-001.json
```

Do not silently suppress the optional real-DNCA smoke test: a skipped test
is **not** experimental evidence. The offline validation runner includes
a mandatory oracle-blind test and the fixed-base theorem regression; its
required-test stage must report a valid JUnit result.

## 5. What has actually been checked

- A source-equivalent pure-Python copy of
  `dnca_signal_identifiability.py` passed **14/14 tests** locally.
- Among those, 5,000 deterministic property-trial configurations produced
  **zero strict inversions** under the common-scalar transform.
- Demonstrated that signed per-claim cues *can* invert an ordering,
  that gain-zero preserves scores and that hidden labels do not affect
  the selection function.
- No real-DNCA claimwise output has been executed in this session;
  no new significance test or calibrated checkpoint exists.
- Full GitHub monorepo pytest/ruff/mypy and all Actions remain **UNVERIFIED**.

These checks support a **narrow deterministic software/math statement**,
not cognitive advantage or truth verification performance.

## 6. Scientific acceptance and falsification gates

Before attributing a benefit to DNCA, pre-register: (i) checkpoint and
data hashes; (ii) separate *held-out* benefit oracle; (iii) real inference
and independent verification costs; (iv) paired seeds/tasks; (v) non-neural
baseline with equal processing tools, uncertainty-only and expected
verified-benefit-per-cost comparators; (vi) signal sign reversal and
within-task-block permutation; (vii) proper paired uncertainty intervals
and a practical, not merely statistical, gain threshold; (viii) anti-leakage
tests and independent reproduction.

Reject the advantage hypothesis (under a qualified instrument and
informative power) when claim-specific signals fail to predict extra
independent verified benefit at fixed total resource cost. If these
preconditions fail, the only permissible verdict is **UNTESTED or
INADMISSIBLE**, not either PASSED or KILLED.

**⊛ First principle:** a system cannot learn to direct attention merely
by adding the same motivational scalar to every candidate's score.
Identifying *which* candidate deserves attention is a separate causal and
statistical problem from modulating *how much* attention exists.
