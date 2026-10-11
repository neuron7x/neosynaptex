# Research direction

claim_status: derived

Canonical since 2026-10-11. Subordinate to `CANONICAL_POSITION.md` and
`docs/CLAIM_BOUNDARY.md`; where they are stricter, they win.

## 1. What the evidence in this tree says

| # | finding | status | source |
|---|---|---|---|
| F1 | The repo's own γ estimators return γ̂ inside the METASTABLE band for inputs with no critical dynamics: linear 1/f noise (1.016 ± 0.058, 10/10 seeds), AR(1) φ=0.9 (0.863 ± 0.107, 5/10 seeds), and `cost := 1/topo` (exactly 1.0, verdict METASTABLE). | measured | `results/gamma_specificity/run_v1.json` |
| F2 | On the 69-subject HRV dev cohort the IAAFT null — the only layer that preserves the power spectrum — is separable in 4/69 subjects for DFA α and 7/69 for sample entropy. | measured | `evidence/surrogates/null_suite_summary.json`, `evidence/surrogates_sampen/null_suite_summary.json` |
| F3 | The same two files report an overall verdict of SEPARABLE for 68/69 and 66/69 subjects. That label comes from a "3 of 5 layers" rule satisfied by nulls that destroy the spectrum (shuffled, Poisson). | measured | same files, `config.required_separable_layers` |
| F4 | On `serotonergic_kuramoto` the IAAFT smoke screen returned NULL_NOT_REJECTED, and the p-value depends on which vector is surrogated. | measured | `docs/audit/PHASE_3_SMOKE_RESULT.md` |
| F5 | Replication registry: 1 support, 1 theory_revision, 3 pending. | measured | `evidence/replications/registry.yaml` |

## 2. What follows, and what does not

γ as estimated here is a second-order statistic: a slope of a power spectrum or of
a log–log cloud. Any linear Gaussian process with the same spectrum reproduces it
(F1), and where the spectrum is held fixed the tested signals are mostly not
distinguishable from their surrogates (F2, F4).

Follows: **measuring γ̂ ≈ 1 on a new substrate cannot, by itself, add evidence for
or against a critical regime.** The estimand has to change before more substrates
are measured.

Does not follow: "the hypothesis is dead". F1 shows the instrument is not
specific; it says nothing about whether critical systems also produce γ ≈ 1.
`docs/audit/PHASE_4B_CANONICAL_KURAMOTO_OBSERVABLES.md` forbids that conclusion
and this document does not draw it.

## 3. The question

> Is there an observable that (a) carries information beyond the linear spectrum
> and (b) tracks a controlled distance to a known critical point — and does it
> (c) survive on real data out of sample?

Each stage has its falsifier fixed before it is run.

**G0 — instrument on ground truth (simulation).**
Simulators with an analytically known critical point: Kuramoto (K_c) and a
branching process (σ = 1). A candidate statistic passes only if it changes
monotonically with distance to the critical point *and* fails to fire on
spectrum-matched IAAFT surrogates of the critical run and on the F1 generators.
Thresholds, seeds and sample sizes are committed before the first run.
*Kill:* no candidate passes both halves → the programme stops at G0 and the
result is published as a negative.

*Outcome (2026-10-11):* **G0_FAIL** — see §3.1.

**G1 — nonlinear structure in the existing HRV cohort.**
Already run: negative for DFA α and for sample entropy (F2). Closed. No further
HRV γ work.

**G2 — states of consciousness, open EEG data.**
Complexity markers (Lempel–Ziv, permutation entropy, sample entropy) against
IAAFT surrogates, with the 1/f exponent as a competing covariate, scored as
leave-subject-out ΔAUC over the exponent alone.
*Kill:* the ΔAUC interval includes 0 → the markers add nothing beyond the
spectrum. Status: **hypothesized**; no dataset has been acquired or inspected,
and G2 does not start before G0 passes.

### 3.1 G0 outcome — G0_FAIL (measured, 2026-10-11)

Pre-registration `experiments/g0_ground_truth/PREREGISTRATION.md` (commit
`aa9b3455`, before the harness existed); evidence
`results/g0_ground_truth/run_v1.json`, byte-reproducible, bound to both the
harness and the pre-registration by sha256. 10 seeds, 99 IAAFT surrogates.

| statistic | (a) tracks distance, median abs ρ — Kuramoto / branching | (b) IAAFT rejections at p/p_c = 0.98 — Kuramoto / branching | passes |
|---|---|---|---|
| time-reversal asymmetry | 0.09 / 0.39 — fail | 0/10 / 1/10 | no |
| permutation entropy | 0.80 / 0.89 — fail | 0/10 / 1/10 | no |
| Lempel–Ziv complexity | 0.99 / 0.96 — pass | 0/10 / 0/10 | no |
| γ̂ (method control) | 0.91 / 0.96 — pass | 0/10 / 0/10 | — |

Criterion (c) held everywhere (at most 1/10 rejections on the linear
generators). The method control behaved as required (γ̂ never passed (b)), and
the harness's own liveness test shows the same procedure does reject a known
time-irreversible series, so "no rejection" is a result and not a dead
instrument.

What this says:

1. Distance to the critical point **is** trackable in both simulators — by
   Lempel–Ziv complexity and by γ̂ itself.
2. Near the critical point neither is distinguishable from an IAAFT surrogate.
   In these two systems, at this size, the approach to criticality from below is
   visible only through the power spectrum; it is the lengthening of a
   correlation time, which a linear process has too.
3. γ̂ does not sit at 1 near the critical point. Mean γ̂ along the grid
   p/p_c = 0.50 … 0.98: Kuramoto 0.77, 0.99, 1.22, 1.45, 1.67, 1.70, 1.80;
   branching 0.04, 0.05, 0.15, 0.25, 0.83, 1.30, 1.88. It crosses the METASTABLE
   band at p/p_c ≈ 0.6 (Kuramoto) and between 0.90 and 0.95 (branching), and is
   ≈ 1.8–1.9 at 0.98. Where it crosses depends on where the fit band lies
   relative to the correlation time (derived, not separately tested).

By the kill rule fixed in §3, **the programme stops at G0.** G2 is not started.

Limits, as pre-registered: subcritical side only; mean-field systems with
N = 500, n = 4096; three candidate statistics; two simulators are not critical
systems in general. A different candidate set or a supercritical/finite-size
design is a new experiment with its own pre-registration, reported beside this
one.

## 4. Rules that apply from now on

1. A verdict that aggregates null layers must report the IAAFT layer on its own
   line. "k of n layers" is not admissible as a headline (F3).
2. No new substrate adapter, and no promotion of an existing ledger entry, until
   G0 has a recorded outcome.
3. A statistic is not called a marker of criticality unless it has passed G0.
4. `tests/test_gamma_specificity.py` keeps F1 reproducible; if an estimator
   change makes it NO_COUNTEREXAMPLE_FOUND, that is a result to report, not a
   test to fix.

## 5. Tracks set aside

| track | where it is | why |
|---|---|---|
| `serotonergic_kuramoto` adapter v2 (`_N_SWEEP=128`, log-uniform sweep) | tag `archive/2026-10-11/feat/phase-4-substrate-resolution` | changes a ledger-bound adapter hash without re-deriving γ; a denser sweep does not address F1 |
| Neurophase RUN1 pipeline inside this repo | tag `archive/2026-10-11/feat/neurophase-run1-pipeline` | its locked verdict was produced from a 4-subject synthetic self-test; no tests |
| Manuscript drafts under `manuscript/` | in tree, unchanged | written before F1–F3; not to be submitted in the current form |
| Cross-substrate γ ≈ 1 survey | `evidence/gamma_ledger.json`, unchanged | frozen as a historical record by rule 2 |

## 6. Not known

- Whether the G0 negative holds on the supercritical side, at larger N, or for
  spatially extended (non-mean-field) critical systems.
- Whether F1 holds for the other estimators in the tree (FDT, DFA-based); only
  `fit_hrv_gamma` and `core.gamma.compute_gamma` were probed.
- Which open EEG datasets are usable for G2.
