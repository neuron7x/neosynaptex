# DOPA / DNCA — Synthetic Signal Instrument Sensitivity v1

**Class:** executed synthetic positive/null control and research-method validation.
**Scientific status:** NOT A DNCA EXPERIMENT; DOPA-CLOSURE remains UNTESTED.
**Date:** 2026-10-16.

## Research question

Can a fixed-budget verification-priority metric distinguish an informative,
claim-aligned auxiliary signal from a signal independent of eventual verification
benefit, without evaluating only the invariant *mean* of priority scores?

**Answer for this simulated instrument:** yes, under the explicitly scripted
data-generating process and the finite recorded seed. The observation establishes
only instrument sensitivity; it does not show that any existing DNCA model
generates useful signals.

## Exact definitions

For each synthetic claim `i`, let:
- `y_i ∈ {0,1}`: hidden benefit of selecting the claim, available **only**
  to the evaluator after the routing policy commits to a choice.
- `z_i ∈ [0,1]`: noisy baseline uncertainty proxy; synthetic, partly
  correlated with `y_i`.
- `s_i ∈ [-1,1]`: synthetic auxiliary signal generated in two regimes:
  **informative** (noisy oracle-dependent cue) or **null** (independent uniform).
- `g = 0.25`: predeclared signal gain.
- `k = 16`: identical number of routing selections for every policy.
- `n = 128`: candidates per trial, with 128 seeded replicates per regime.

The baseline ranks `z_i`; the modulated policy ranks `z_i + g*s_i`.
The permuted control shuffles `s_i` across candidates before ranking.
The sign-reversed control ranks `z_i - g*s_i`. Random selection uses
a fixed PRNG; an oracle ceiling uses withheld `y_i` **only** as an
upper bound, never as a deployable policy.

The primary synthetic metric is `sum(y_i)` among the `k` selected claims,
so each reported mean is **correctly selected claims per 16 slots**.
It is **not** a real verified-closure count, model accuracy or
verification utility measured in the external world.

## Locally executed result

Executed in a Python 3.13.5 sandbox with pytest 9.0.2:

```bash
python -m pytest -q tests/dopa_closure_v2/test_synthetic_signal_instrument.py
# 12 passed in 0.31s
python -m experiments.dopa_signal_validity.paired_instrument \
  --output /tmp/synthetic_control_run.json
```

The repository's full test suite and DNCA integration were **not** executed.

| Regime | Uncertainty-only | Modulated | Shuffled cue | Reversed cue | Random | Oracle |
|---|---:|---:|---:|---:|---:|---:|
| Informative synthetic cue | 10.5703 | 14.9609 | 9.7813 | 3.7969 | 5.8047 | 16.0 |
| Independent null cue | 10.5156 | 9.7891 | 9.8047 | 9.7734 | 5.6797 | 16.0 |

Observed paired gain over uncertainty:
- **Informative cue:** +4.390625 selected beneficial claims per trial;
  illustrative seeded paired bootstrap interval [4.125, 4.671875].
- **Null cue:** −0.7265625 per trial;
  interval [−0.984375, −0.484375].

Interpretation: injected useful information can improve a fixed-slot selection
policy; injected uninformative noise can degrade it. The simulation was
constructed to give an informative cue via `y_i`: **this result is a positive
control, not an independent discovery**. The bootstrap intervals describe only
synthetic trial variability; they do not justify claims about real agents.

## Artifact integrity

- Git source blob for
  `experiments/dopa_signal_validity/paired_instrument.py`:
  `8946876adef624720444aed499e6782946fef869`.
- Git test blob:
  `bc18d9e840fd4b0898ec27272a59530e25adea33`.
- Git archived raw-result blob:
  `57866abe418c555f28994e67a489d05d9c15aedd`.
- Raw JSON SHA-256:
  `6342e56642f6e8726bda1bf25155057cbd9f4589e7204af9b82bbd29fe0ec841`.
- Result's inner `payload_sha256` field covers canonical JSON **before**
  adding that field:
  `7de320e991173d4eb8c991b961720a0214d25d1cc886f3f4836bf9ca071ef9b7`.

The Git source/test blob identifiers above were cross-checked against the
identical Python source and test files actually executed locally. The archived
JSON blob was cross-checked against the locally produced raw result. These
identifiers are content-integrity checks, **not signatures**, and are
not external scientific replication.

## Validation and next experiment

To move beyond this calibration, replace the cue `s_i` with actual,
frozen, real DNCA output; use an independent domain-qualified verifier and
held-out task outcomes. Include an uncertainty-only baseline, permuted
within-batch signals, signed reversal, gain zero and an informed non-neural
cost-aware policy.

**Critical missing factor:** all current policies spend exactly `k` slots,
but the costs of computing the cue, neural forward passes, verification CPU/GPU
or API tokens are not metered. Accordingly **resource efficiency cannot be
claimed**. Measure total end-to-end spend before proposing causal or
performance superiority.

**Promotion invariant:** passing this positive/null control qualifies the
*simulated routing instrument* to be tested on real data; it does not
qualify DNCA's signal, the independent evidence chain or the cognition
hypothesis.

**⊛ Quintessence:** A metric must respond differently to information and
noise **before** it can be trusted to evaluate real agent intelligence.
