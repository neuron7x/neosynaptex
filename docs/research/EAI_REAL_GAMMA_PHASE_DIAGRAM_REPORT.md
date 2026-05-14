# EAI Real-Data γ-Ledger Phase Diagram v1 — Report

> Companion to
> [`EAI_REAL_GAMMA_PHASE_DIAGRAM_V1.md`](EAI_REAL_GAMMA_PHASE_DIAGRAM_V1.md)
> (pre-registration). Records the verdict and the path to it.

## 0. Verdict

**VERDICT: `NO_SEPARABLE_REGION_FOUND`**

Decisive. Honest. The STN-analog graded-falsification hypothesis,
which survived in PR #196's synthetic phase diagram
(`PHASE_REGION_FOUND` with 117 useful cells across 3 separable
zones), **does not survive on real data**.

| metric | value |
|---|---:|
| total_cells | 490 (10 substrates × 7 probe sets × 7 evidence_path_count) |
| useful_global | **0** |
| regression_global | **0** |
| null_global | **490** (graded == binary on every cell) |
| verdict | **NO_SEPARABLE_REGION_FOUND** |

## 1. What this measures

The 10 γ-ledger entries (read-only via the unmodified PR #193
`gamma_bridge`) are fed through both gates under:
- 7 probe-count values (0..6 probes from a fixed canonical pool)
- 7 evidence_path_count values (0..6 synthetic revalidation paths)

For every one of the 490 cells, the graded gate emits an
identical verdict to the binary gate.

## 2. Why the graded gate produced zero signal

The canonical probe pool is a small set of token-overlap adversarial
phrases ("universal scaling validated cross substrate",
"every measured substrate converges to one", etc.). On synthetic
PR #196 templates, these probes shared 2+ tokens with the
synthetic claim text by construction, triggering graded
`conflict_strength > 0`.

On real γ-ledger description text (e.g.
"Wild-type zebrafish calcium imaging — topological complexity vs
thermodynamic cost") the probes share at most 1 unique token. The
token-overlap threshold (≥2 unique shared tokens) is not reached,
so `falsification_decision_graded` returns
`conflict_strength = 0.0` — equivalent to the binary path. Real
claim vocabulary does not overlap with the probe vocabulary.

The synthetic grid in PR #196 was the *cause* of separability.
The vocabulary distribution of the templates I generated was
unintentionally aligned with the probe vocabulary. Real claims
are not aligned.

## 3. Hypothesis status

| Layer | Outcome |
|---|---|
| Synthetic 120-row dataset (PR #195) | NULL_RESULT |
| Synthetic 20736-cell grid (PR #196, post-Codex fix) | PHASE_REGION_FOUND |
| **Real 490-cell γ-ledger grid (this PR)** | **NO_SEPARABLE_REGION_FOUND** |

The conjunction across the experimental program is clear: the
STN-analog graded falsification has **no measurable operational
value on the real γ-ledger** at the pre-registered constants
(`+0.4` per substring hit, `+0.15` per token-overlap hit,
`required_paths = ceil(1 + conflict_strength * 2)`).

**The hypothesis is locally dead** on this dataset.

## 4. What this artifact ships (despite NO_SEPARABLE_REGION_FOUND)

Per CC-META-001 ROOT-3 ("failure preserved as artifact is
superior to failure hidden as silence"):

1. `core/eai/real_gamma_phase_diagram.py` — pure library composing
   PR #193 gamma_bridge + PR #196 graded_gate; γ-ledger is
   read-only.
2. `tools/eai/run_real_gamma_phase_diagram.py` — deterministic
   runner; 3 byte-identical artifacts per run.
3. `tests/eai/falsification/test_real_gamma_phase_diagram.py` —
   13 invariant tests + REGRESSION_ANCHOR pinning the
   `NO_SEPARABLE_REGION_FOUND` verdict.
4. `.github/workflows/eai-real-gamma-phase-diagram.yml` — CI gate
   enforcing 7 read-only invariants on PR #193/#195/#196 anchors
   and on production engine.
5. `artifacts/eai/phase_diagrams/real_gamma_phase_diagram_v1.{json,csv,md}` —
   the deterministic transcript.

## 5. What does NOT ship

- No constant tuning. The `+0.4 / +0.15 / ceil(1+c*2)` numbers
  remain the pre-registered values.
- No graded-gate promotion. The graded primitive stays in the
  repo as DIAGNOSTIC-ONLY tooling. It is NOT wired into
  `core/eai/engine.py`. The production engine remains the binary
  IEV path used by all four prior PRs.
- No claim that the γ-ledger is now epistemically validated or
  refuted; this report measures the gate's behaviour, not the
  ledger's truth.

## 6. Why the graded gate stays in the repo

Killing the graded_gate / graded_phase_diagram modules outright
would lose the **diagnostic capability**: future PRs might want
to re-measure on a different probe pool, different real datasets
(EEG, HRV, financial), or different threshold formulas. The
infrastructure is cheap to keep and zero-cost to ignore. Its
production status is `archived-diagnostic-only`.

## 7. Why the repo is NOT deleted

The graded-falsification sub-thread is one of five experimental
threads on this repo. The other four are net positive:

| PR | Artifact | Independent of STN-analog? |
|---|---|---|
| #192 | EAI engine + false-promotion benchmark v1 | YES |
| #193 | γ-ledger ↔ EAI bridge (admissibility=0.2857) | YES |
| #194 | Admissibility tracker + bypass-resistant CI gate | YES |
| #195 | Falsification protocol + benchmark v1_1 | partially (graded primitive used here) |
| #196 | Synthetic phase diagram | YES (the diagnostic survives the verdict flip) |
| **#197 (this)** | Real-data phase diagram | NO_SEPARABLE result kills STN-analog locally |

Independent value of #192/#193/#194 is independent of the STN-analog
verdict. Deleting the repo because one of five hypotheses died
would violate the operator's own discipline
(`CANON-7: Falsification is not failure. Falsification is the
mechanism of progress.`).

## 8. Permitted next moves

Per pre-registration `Permitted next moves`:

- ✅ **NO_SEPARABLE_REGION_FOUND** → archive graded gate as
  diagnostic-only; do NOT pursue further refinement.
- ❌ Do NOT tune constants to chase PHASE_REGION_FOUND on a
  follow-up dataset without fresh pre-registration.
- ❌ Do NOT introduce per-entry probe tuning.
- Optional: a new PR could explore non-EAI gating mechanisms on
  the same real data (e.g. semantic-similarity scores instead of
  token-overlap counts). That is a SEPARATE hypothesis with
  SEPARATE pre-registration.

## 9. CC-META-001 status

- **Gate A (pre-registration)**: PASS — verdict rules + axes +
  ranges + probe pool declared in
  `EAI_REAL_GAMMA_PHASE_DIAGRAM_V1.md` BEFORE this run.
- **Gate D (forbidden claims)**: PASS — forbidden phrasings
  enumerated; report uses permitted statement form throughout.
- **Gate G (final CI)**: pending merge.
- **Claim tier under §8.1**: FALSIFIED for the narrow claim
  "graded falsification produces a separable useful region on
  real γ-ledger data under the canonical probe pool." The
  infrastructure remains TENTATIVE (diagnostic-only).

## Claim boundary

> EAI Real-Data γ-Ledger Phase Diagram v1 reports binary-vs-graded
> gate behaviour across 10 real γ-ledger entries × 7 probe-count
> values × 7 evidence-path-count values, under a fixed canonical
> probe pool. The verdict on the current run is
> `NO_SEPARABLE_REGION_FOUND`. γ-ledger read-only. No production
> engine modified. No claim about γ scaling law, brain mechanism,
> or AGI is asserted.

**Operator law verbatim**:
> If the result is ugly, preserve it. If graded gate is useless,
> say so. ... No rescue tuning. No pretty lie.

We did. The result is `NO_SEPARABLE_REGION_FOUND`. It is
preserved. Graded gate is, by this measurement, useless on real
γ-ledger data.

---

**Run timestamp**: 2026-05-14
**Branch**: `eai/real-gamma-phase-diagram-v1`
**Hypothesis under test**: STN-analog graded falsification on real claim text
**Status**: locally dead, archived as diagnostic-only
**PR #195 + #196 anchors**: preserved (CI-enforced)
**Production engine**: untouched (CI-enforced)
