# EAI Graded Falsification Phase Diagram v1 — Pre-Registration

> Committed BEFORE the phase-diagram tool is executed. Verdict rules,
> grid axes, ranges, metrics, and visualisation outputs are fixed
> here. Post-hoc adjustment of any of them requires a fresh
> pre-registration document with operator authorization.

## Motivation

PR #195 produced VERDICT = NULL_RESULT on the 150-row v1_1 dataset
at the pre-registered constants. The honest read of that finding:
**the hypothesis was not refuted; it was untested at that fidelity**.

Two questions remain:

1. Is there ANY region of input space where graded falsification
   measurably reduces false promotion **without** killing true
   evidence?
2. Is there a region where graded falsification **regresses** true
   evidence (i.e., the STN-analog hypothesis is locally falsified)?

A phase diagram is the right instrument. A single experimental
point (PR #195) is replaced by a 6-axis deterministic grid; each
cell receives a binary verdict and a graded verdict; the cells are
then classified into regions.

This PR is **diagnostic**. It does NOT promote graded falsification
to production. It does NOT modify PR #195's NULL_RESULT anchor.

## Primary hypothesis

> Graded falsification outperforms binary gating **only** in regions
> where:
>   conflict_strength exceeds the binary ambiguity threshold
>   AND evidence_path_count is insufficient under graded requirement
>   AND true evidence retains enough support paths to survive
>       threshold modulation.

Outside that conjunction, graded should either equal binary (NULL
region) or regress (REGRESSION region).

## Grid axes (fixed, byte-exact)

```
conflict_marker_count: integer in [0, 8]            (9 values)
evidence_path_count:   integer in [0, 8]            (9 values)
claim_class:           {true_bounded, false_obvious,
                        false_subtle, ambiguous,
                        adversarial_authority,
                        adversarial_boundary_expansion,
                        adversarial_fake_citation,
                        adversarial_software_no_execution}
                                                    (8 values)
contradiction_density: {none, low, medium, high}    (4 values)
revalidation_state:    {passed, failed}             (2 values)
boundary_state:        {valid, missing, expanded,
                        contradictory}              (4 values)

total cells = 9 * 9 * 8 * 4 * 2 * 4 = 20736
```

### Axis semantics

- **conflict_marker_count (N)**: how many falsifier markers are
  passed to the gate.
- **contradiction_density**: fraction of those N markers that
  appear in the claim text (or its token set):
    - `none`   → 0 markers actually match
    - `low`    → ceil(N/4) markers match
    - `medium` → ceil(N/2) markers match
    - `high`   → N markers match
- **claim_class**: determines (a) the claim_text template,
  (b) whether matching falsifiers fire as full-substring vs
  token-overlap-only, (c) the *expected* status absent gate
  interference.
- **evidence_path_count**: number of entries in
  `EvidenceArtifact.revalidation_evidence_paths` available to
  the graded gate.
- **revalidation_state**: `revalidation_passed` argument to
  both gates.
- **boundary_state**: shape of `BoundaryCard`:
    - `valid` → `valid_for=[substrate]`, `invalid_for=[]`, tested ⊆ valid
    - `missing` → `valid_for=[]`
    - `expanded` → `valid_for=[substrate, "global", "universal"]`
    - `contradictory` → `valid_for ∩ invalid_for non-empty`

## Per-cell evaluation

For each grid cell, both gates are run on a synthesised
`(claim, falsifiers, artifact)` triplet and the following
per-cell record is produced:

```jsonc
{
  "cell_id": "C-...",         // deterministic from axis tuple
  "axes": { ... },            // the 6 axes echoed back
  "binary": {
    "verdict": "EVIDENCE|KILLED|QUARANTINED",
    "reason": "..."
  },
  "graded": {
    "verdict": "EVIDENCE|KILLED|QUARANTINED",
    "reason": "...",
    "conflict_strength": <float>,
    "required_paths": <int>,
    "available_paths": <int>
  },
  "expected_status": "EVIDENCE|KILLED|QUARANTINED",
  "graded_reduced_false_promotion": <bool>,
  "graded_killed_true_evidence":    <bool>,
  "graded_quarantined_ambiguous":   <bool>
}
```

## Per-claim-class metrics

For each claim_class, aggregated over all 2592 cells in that class:

```
binary_false_promotion_rate    = FP_binary / non_evidence_total
graded_false_promotion_rate    = FP_graded / non_evidence_total
binary_true_positive_rate      = TP_binary / evidence_total
graded_true_positive_rate      = TP_graded / evidence_total
graded_delta_false_promotion   = graded_FPR - binary_FPR
graded_delta_true_positive     = graded_TPR - binary_TPR
quarantine_delta               = graded_quar_count - binary_quar_count
regression_cells_count   = cells where expected=EVIDENCE and graded=KILLED
useful_cells_count       = cells where expected!=EVIDENCE and binary=EVIDENCE
                                  and graded ∈ {KILLED, QUARANTINED}
null_cells_count         = cells where binary == graded
```

## Global verdict rules (pre-registered)

| Verdict | Condition |
|---|---|
| `PHASE_REGION_FOUND` | at least one of `false_subtle`/adversarial classes has `graded_false_promotion_rate < binary_false_promotion_rate` AND `true_bounded.regression_cells_count == 0` in the same boundary/revalidation parameter zone |
| `NO_SEPARABLE_REGION_FOUND` | graded never improves false promotion without harming true evidence |
| `REGRESSION_REGION_FOUND` | graded reduces false promotion **only** by killing true evidence (i.e., useful_cells_count > 0 ⇒ regression_cells_count > 0) |
| `INVALID_EXPERIMENT` | grid missing axes; non-deterministic output; PR #195 anchor modified; production engine changed |

## Hard invariants (CI-enforced)

1. The grid is exhaustive: every combination of axes appears.
2. The runner is deterministic — two consecutive runs produce
   byte-identical JSON.
3. `tools/eai/run_falsifiability_test.py` (PR #195) is **not modified**.
4. `artifacts/eai/benchmarks/falsifiability_test_v1_report.json`
   (PR #195) is **not modified**.
5. `tests/eai/calibration/test_falsifiability_v1.py::test_current_verdict_is_null_result_regression_anchor`
   continues to pass.
6. `core/eai/engine.py` and `core/iev_gate.py` are unchanged
   (production engine untouched).
7. Negative regions (regression / null) are NEVER hidden from the
   summary report.

## Outputs (byte-exact paths)

```
artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.json
artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.csv
artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_summary.md
```

## Permitted next moves (after verdict)

- `PHASE_REGION_FOUND` → dataset v2 with pre-registered constants
  targeting the discovered region; remain DIAGNOSTIC-ONLY until
  external replication.
- `NO_SEPARABLE_REGION_FOUND` → keep graded primitive as diagnostic
  library; do NOT promote to production engine.
- `REGRESSION_REGION_FOUND` → abandon graded gate; preserve the
  finding as documented null artifact.
- `INVALID_EXPERIMENT` → rebuild; do NOT proceed.

## Forbidden phrasings (binding for this PR)

- "phase diagram proves STN architecture"
- "graded gate validated in region X"
- "supported across all classes"
- "phase v1 confirms hypothesis"
- "production-ready graded gate"
- "scientific result"

Permitted statement form:

> The phase diagram identifies cells where graded falsification
> changes the gate verdict relative to binary on the synthetic
> 6-axis grid; classification of those cells into useful /
> regression / null regions is reported. No production behaviour
> changes.

## Claim boundary

> EAI Graded Falsification Phase Diagram v1 maps the behavioural
> difference between binary and graded gates over a deterministic
> 6-axis synthetic grid. Outputs are diagnostic JSON/CSV reports.
> No production engine is modified. No claim about substrate
> behaviour, brain mechanism, or AGI is asserted.

---

**Pre-registered**: 2026-05-14 (commit pending)
**Status under CC-META-001 §8.1**: HYPOTHESIS until experiment runs;
post-run claim tier is FALSIFIED / TENTATIVE depending on verdict.
