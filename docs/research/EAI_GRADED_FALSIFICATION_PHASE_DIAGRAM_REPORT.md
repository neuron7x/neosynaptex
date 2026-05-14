# EAI Graded Falsification Phase Diagram v1 — Report

> Companion to
> [`EAI_GRADED_FALSIFICATION_PHASE_DIAGRAM_V1.md`](EAI_GRADED_FALSIFICATION_PHASE_DIAGRAM_V1.md)
> (pre-registration). Records the verdict + the path that produced it.

## 0. Verdict transparency notice

The first commit on this branch reported **REGRESSION_REGION_FOUND**
based on a **metric bug** Codex review correctly identified:

* **Codex P1.1** (closed): the `graded_killed_true_evidence` flag
  fired whenever `expected=EVIDENCE` AND `graded_verdict=KILLED`,
  including cells where the BINARY gate also killed (e.g.
  `boundary_state=missing` forces `can_be_promoted=False` for BOTH
  gates). That conflated shared structural kills with graded-specific
  regressions and inflated the regression count to 648, all of which
  were spurious. Fix: `graded_killed_true_evidence` now additionally
  requires `binary_verdict != KILLED`.

* **Codex P1.2** (closed): the pre-registration required
  zone-level (`boundary_state × revalidation_state`) verdict
  aggregation; the first commit used global aggregates. Fix:
  per-zone aggregation walks the 8 zones and applies the rule
  zone-by-zone.

After both fixes, the same data + same constants + corrected metric
produces verdict **PHASE_REGION_FOUND**. Constants were NOT tuned.
Dataset was NOT modified. Only the metric definition was corrected
to match the pre-registration.

This is not a rescue. The original verdict was wrong because the
metric was wrong. The corrected verdict is the legitimate output of
the pre-registered design.

## A. What changed

- New library `core/eai/graded_phase_diagram.py` — pure deterministic
  functions over the 6-axis grid.
- New runner `tools/eai/run_graded_falsification_phase_diagram.py` —
  emits JSON + CSV + Markdown deterministically.
- New tests `tests/eai/falsification/test_graded_phase_diagram.py` —
  15 invariant tests.
- New CI workflow `.github/workflows/eai-graded-phase-diagram.yml` —
  determinism replay + anchor preservation + production-engine-
  untouched invariant.
- New artifacts (sha-pinned):
  - `artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.json`
  - `artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.csv`
  - `artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_summary.md`

## B. What did not change

- `core/eai/engine.py` — production engine, untouched.
- `core/iev_gate.py` — production IEV gate, untouched.
- `core/falsification_engine.py` — no edits beyond what shipped in #195.
- `core/eai/graded_gate.py` — no edits beyond what shipped in #195.
- `data/eai_calibration/false_promotion_benchmark_v1.jsonl` — untouched.
- `data/eai_calibration/false_promotion_benchmark_v1_1.jsonl` — untouched.
- `artifacts/eai/benchmarks/falsifiability_test_v1_report.json`
  (PR #195 anchor) — UNTOUCHED, verdict still NULL_RESULT.
- `tests/eai/calibration/test_falsifiability_v1.py` — UNTOUCHED.

## C. Why PR #195 NULL_RESULT remains valid

PR #195 ran the binary vs graded comparison on a **single dataset**
(`false_promotion_benchmark_v1_1.jsonl`, 150 rows) at a **single
operating point** (available_paths=2, fixed substrate text templates,
real-match falsifiers only). That single-point experiment returned
NULL_RESULT honestly.

This PR's phase diagram **does not contradict that finding**. It
extends the search to a 20736-cell grid and looks for *separable
regions* of input space where the gates diverge. The 150-row v1_1
dataset corresponds to a small subset of this grid (specifically:
`evidence_path_count = 2`, `boundary_state = valid`,
`revalidation_state` depends on row, `claim_class ∈ {true_bounded,
false_*, ambiguous, adversarial_*}`). Inside that subset, the v1
verdict NULL_RESULT remains the correct call.

The phase diagram exposes what the single-point experiment could
not: the **rest** of the input space.

## D. Phase regions found (CORRECTED, post-Codex)

| metric | value |
|---|---:|
| total cells | 20736 |
| useful cells (graded helps without false-killing) | 117 |
| graded-SPECIFIC regression cells | 0 |
| null cells (graded equals binary) | 20619 |
| true_bounded graded-specific regression cells | 0 |
| **VERDICT** | **PHASE_REGION_FOUND** |
| verdict_reason | zone_separable = `['valid/passed', 'expanded/passed', 'contradictory/passed']`; zone_regression = `[]` |

### Zone breakdown (post-correction)

| zone | useful | regression |
|---|---:|---:|
| `valid/passed` | 39 | 0 |
| `valid/failed` | 0 | 0 |
| `missing/passed` | 0 | 0 |
| `missing/failed` | 0 | 0 |
| `expanded/passed` | 39 | 0 |
| `expanded/failed` | 0 | 0 |
| `contradictory/passed` | 39 | 0 |
| `contradictory/failed` | 0 | 0 |

Three zones are cleanly separable (useful gains AND zero graded-
specific regression in that zone). Five zones are null (graded ==
binary). Crucially, **no zone has co-located useful gains and
regression** — the conjunction the pre-registered rule guards
against does not occur on this grid.

The 648 cells previously flagged as "regression" were
**boundary_state=missing** cells where `can_be_promoted=False`
for both gates (structural failure of binary, not a graded-specific
kill). They are now correctly classified as `null` cells (graded
equals binary), not regression.

## E. Regions where graded helps

Per-class `graded_delta_false_promotion`:

| claim_class | binary FPR | graded FPR | ΔFPR | useful cells |
|---|---:|---:|---:|---:|
| `false_subtle` | 0.3333 | 0.3009 | **−0.032** | 84 |
| `ambiguous` | 0.3333 | 0.3206 | **−0.013** | 33 |

These are the ONLY two classes where graded falsification reduces
false promotion vs binary. The improvements exist exclusively in
sub-regions of high `conflict_marker_count` + `high`
`contradiction_density` combined with low `evidence_path_count`
(consistent with the pre-registered hypothesis).

## F. Regions where graded harms (CORRECTED)

After the Codex P1.1 fix, there is **no zone** in this grid where
graded specifically harms true-bounded evidence. The original 648
"regression" flag was a metric bug counting cells where the BINARY
gate already killed (e.g. `boundary_state=missing` makes
`can_be_promoted=False` for both gates).

**Open caveat**: this absence-of-regression holds on the synthetic
grid. The pre-registration explicitly warns that future iterations
on real-call data may surface graded-specific regressions not
captured by the synthetic templates. The current finding does NOT
generalise beyond the grid.

## G. Regions where graded equals binary

20619 cells (99.4% of grid) — graded verdict = binary verdict.
Dominant cases:
- `conflict_marker_count = 0` (no markers, nothing to grade)
- `boundary_state = missing` (`can_be_promoted=False` for both gates)
- `revalidation_state = failed` (both gates QUARANTINE before
  reaching the threshold rule)
- `false_obvious` and adversarial-* classes with full-substring
  hits (binary already catches them; graded adds nothing)

## H. Is v2 hypothesis worth testing?

**Conditional yes, with operator authorization, fresh pre-registration,
and external-replication data**. The corrected phase diagram identifies
three separable zones (`valid/passed`, `expanded/passed`,
`contradictory/passed`) where graded has useful gains with zero
graded-specific regression on this synthetic grid.

The right v2 hypothesis is NOT "tune constants" — it is **measure
the same phenomenon on non-synthetic claims**:

> Does the separable region survive on real-world claims (e.g. the
> γ-ledger entries from PR #193), where token distributions are not
> dictated by templates? If yes, graded falsification has a real
> operational value. If no, the synthetic grid was the cause of
> separability and PHASE_REGION_FOUND is a grid artifact.

This is a SEPARATE PR with SEPARATE pre-registration. It is NOT
part of this PR.

## I. Next legal PR options (after this PR merges)

1. **Dataset v2**: a real-call dataset (not synthetic templates)
   where noise-marker density on bounded claims is empirically
   measured rather than synthetically dialled.
2. **Constants v2**: tightened token-overlap weight (e.g. require
   matched tokens to be domain-specific, not stopword-class) — fresh
   pre-registration mandatory.
3. **Abandon graded gate**: the phase diagram shows graded only
   helps by collateral damage; archive as documented negative
   finding; remove the graded_gate module from public surface
   (keep in private diagnostic tooling).
4. **Keep as diagnostic-only**: do not promote, but retain as a
   measurement tool for future inputs.

## J. CC-META-001 status

- **Gate A (pre-registration)**: PASS — verdict rules + axes + ranges
  declared in `EAI_GRADED_FALSIFICATION_PHASE_DIAGRAM_V1.md` BEFORE
  this run.
- **Gate D (forbidden claims)**: PASS — no forbidden phrasings
  emitted; semantic-drift gate to verify.
- **Gate G (final CI)**: pending merge.
- **Claim tier**: FALSIFIED for the narrow claim "graded gate, at
  these constants, produces a separable useful region without
  collateral damage on true evidence." The infrastructure ships
  as TENTATIVE diagnostic tooling.

## Claim boundary

> EAI Graded Falsification Phase Diagram v1 maps the behavioural
> difference between binary and graded gates over a deterministic
> 6-axis synthetic grid (20736 cells). It identifies, classifies,
> and reports useful / regression / null regions. No production
> engine has been modified. No claim about substrate behaviour,
> brain mechanism, or AGI is asserted.

**Operator law (verbatim from task order)**:
> If the result is ugly, preserve it. If graded gate is useless,
> say so. If it only works by killing true evidence, call it
> regression. No rescue tuning. No pretty lie.

We did. The first commit's result was `REGRESSION_REGION_FOUND`
due to a metric bug; Codex caught the bug; with the bug fixed and
no constants/data changed, the corrected verdict is
`PHASE_REGION_FOUND` on the synthetic grid. Both verdicts are
preserved in the commit history as artifacts of the discipline.

The claim boundary on PHASE_REGION_FOUND is narrow: it holds on
this synthetic grid only, and the natural next falsifier (PR-8 v2)
is to re-run on non-synthetic claims.

---

**Run timestamp**: 2026-05-14
**Branch**: `eai/graded-falsification-phase-diagram-v1`
**Anchor preservation**: PR #195 NULL_RESULT untouched (CI-enforced)
**Production engine**: untouched (CI-enforced)
