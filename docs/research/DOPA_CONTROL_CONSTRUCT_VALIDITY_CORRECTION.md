# DOPA-CLOSURE — Construct-Validity Correction C8

**Status:** source-level repair of non-informative proxy controls.
**Scientific result:** none. DOPA-CLOSURE remains **UNTESTED**.

## Exact defect

In the old `run_controls`, the priority list was randomly permuted and
its **mean** reported as a negative control. For every finite vector
`p=(p1,...,pn)` and permutation `π`,

```text
mean(p) = (1/n) ∑ p[i] = (1/n) ∑ p[π(i)] = mean(permuted(p)).
```

Therefore the negative-control statistic is **mathematically blind** to
misrouting. Two priority allocations can differ completely in which claim
receives attention, yet produce identical means. Additionally, comparing
averages of unrelated proxy scales (priority vs margin, risk, random uniform)
does not measure actual verification utility, accuracy, verified closure, cost
or causal informativeness.

A `passed` Boolean based on superiority over those incomparable means is a
construct-validity failure. A low p-value or a deterministic reproduction of
this procedure would not repair the construct substitution.

## Repair (minimal and backward-aware)

- Retain existing numeric diagnostic fields for historical readers.
- Explicitly report `validity = UNTESTED` and
  `reason = priority_means_cannot_validate_verification_benefit`.
- Set `passed = False` for **all** priority-only diagnostic runs,
  even when the numeric priority means appear larger than proxy means.
- Reject wrong-length, negative, nonfinite or nonnumeric priorities.
- Keep the old offline allocator's instrument verdict `INADMISSIBLE`
  unless separately qualified independent verification exists.
- Add regression tests showing that a swapped claim-priority association
  is **invisible** to the mean statistic.

### Backward-compatibility impact

Any consumer that assumed `controls.passed == True` meant successful
verification must now fail closed. This is intentional. The old result
never justified a meaningful experimental inference.

## Preregistration requirements for a *real* control

Define `i` as a claim, `z_i` as the ex-ante features, `a_i` as the
chosen verification action, `y_i` as a withheld independently checked
truth outcome, `u_i(a_i,y_i)` as verification benefit, and `c_i(a_i)`
as the full measured cost. Compare policies `π` only through

```text
U(π) = [sum_i u_i(π(z_i), y_i)] / [sum_i c_i(π(z_i))]
```

with identical claim sets, a fixed trustworthy oracle, identical
action possibilities, separately measured compute spent on computing
policy scores, matched budgets and paired confidence intervals. The
control must alter the **mapping from claims to actions** (or signal to
policy) and must inspect the resulting outcome, not an invariant summary
statistic. Proper negatives include shuffled claim-to-signal assignments,
DA gain zero and sign reversal with non-even response function. Use
strong uncertainty-only and expected-verification-gain-per-cost baselines.

**Not enough:** comparing a generated priority mean to a random number,
or calling classification accuracy `Verified Closure Rate`.

## Offline checks

```bash
python -m pytest -q tests/dopa_closure_v2/test_control_construct_validity.py
python -m pytest -q tests/dopa_closure_v2/
python -m ruff check core/eai/dopa_controls.py \
  tests/dopa_closure_v2/test_control_construct_validity.py
```

These tests must be *executed* before declaring integration green.
The code change is a validity **constraint**; it is not a performance
result. GitHub CI is unstable, and the whole-suite execution has not
been performed in this update.

**⊛ Principle:** A control is valid only if its measurement is capable
of detecting the hypothesized failure mode. Reproducing a degenerate
statistic perfectly gives reproducible ignorance, not evidence.
