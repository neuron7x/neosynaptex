# EAI Real-Data γ-Ledger Phase Diagram v1 — Pre-Registration

> Committed BEFORE the runner executes. Verdict rules, axes,
> ranges, and probe pool are fixed here. Post-hoc adjustment of
> any of them requires a fresh pre-registration document with
> operator authorization.

## Motivation

PR #196 reported `PHASE_REGION_FOUND` on a 20736-cell synthetic
grid (after Codex P1 metric correction). That verdict had a
known open caveat declared in PR #196 §0 transparency notice:

> The absence-of-regression holds on the synthetic grid. ... The
> current finding does NOT generalise beyond the grid.

This PR is the **direct falsifier** of that synthetic verdict.
We run the binary-vs-graded comparison on **real** γ-ledger
claim texts, not on agent-generated templates. The claim texts
come verbatim from `evidence/gamma_ledger.json` (10 published
substrate entries). The probes are an explicit canonical
overclaim pool, identical for every entry — no per-entry tuning.

## Primary hypothesis (PR #196 carry-over)

> Graded falsification with conflict-modulated IEV threshold
> identifies at least one (substrate × probe-count × evidence_path_count)
> region where graded verdict differs from binary verdict, AND
> this region does NOT regress true evidence on hash-bound entries.

## Pre-registered verdict rules

Identical structure to PR #196 (consistency across the experimental
program):

| Verdict | Condition |
|---|---|
| **PHASE_REGION_FOUND** | at least one zone (`ledger_evidence_tier × ledger_status`) has `useful > 0` AND `regression == 0` |
| **REGRESSION_REGION_FOUND** | useful gains exist only in zones that also regress hash-bound EVIDENCE entries |
| **NO_SEPARABLE_REGION_FOUND** | no useful cells anywhere |
| **INVALID_EXPERIMENT** | non-deterministic output; γ-ledger modified; PR #195/#196 anchors changed; production engine modified |

A **useful cell** = graded verdict ≠ binary verdict AND graded is more
conservative (i.e. graded ∈ {KILLED, QUARANTINED} while binary = EVIDENCE,
OR graded ∈ {KILLED} while binary ∈ {QUARANTINED}).

A **regression cell** = graded ∈ {KILLED} AND binary ∈ {EVIDENCE} on an
entry that the ledger publishes as `EVIDENCE_CANDIDATE` AND whose
`data_sha256` is a valid SHA-256 hex (hash-bound).

A **null cell** = graded verdict == binary verdict.

## Grid axes (fixed, byte-exact)

```
ledger_key          : 10 values (the keys from gamma_ledger.json::entries)
probe_count_used    : integer in [0, 6]      (7 values)
evidence_path_count : integer in [0, 6]      (7 values)

total cells = 10 * 7 * 7 = 490
```

### Probe pool (fixed, canonical, identical for every cell)

Drawn from the same EAI overclaim taxonomy used in PR #196's
`_CLASS_FALSIFIERS`, restricted to the 6 most direct token-overlap
attackers:

```python
PROBES = (
    # token-overlap candidates (no full substring match expected
    # on standard γ-ledger description text):
    "universal scaling validated cross substrate",
    "all substrates demonstrate gamma convergence",
    "production ready scaling law every substrate",
    "every measured substrate converges to one",
    "scientific PASS substrate cohort universal",
    "validated universal gamma across all benchmarks",
)
```

`probe_count_used = k` ⇒ first k probes from `PROBES` are included
as `contradiction_markers` passed to both gates.

## Per-cell evaluation

For each `(ledger_key, probe_count_used, evidence_path_count)` tuple:

1. Read ledger entry via `core.eai.gamma_bridge.ledger_entry_to_gate_inputs`
   (the **unmodified** PR #193 bridge). This produces a deterministic
   `ClaimCard` / `BoundaryCard` / `ReproducibilityManifest` /
   status-tag-derived contradiction_markers from the ledger.
2. **Augment** the contradiction_markers with the first
   `probe_count_used` probes from `PROBES`.
3. Override `revalidation_evidence_paths` on the artifact to length
   `evidence_path_count`.
4. Run binary gate (`falsification_decision` substring + classic IEV
   via `decide_with_graded_threshold(..., conflict_strength=0.0)`).
5. Run graded gate (`falsification_decision_graded` + threshold-
   modulated `decide_with_graded_threshold`).
6. Record both verdicts + reasons + conflict_strength +
   required_paths.

## Per-cell record schema

```jsonc
{
  "cell_id": "C-<ledger_key>-pc<probe_count>-ep<evidence_path_count>",
  "axes": { ... },
  "ledger_meta": {
    "substrate": "...",
    "status": "...",
    "evidence_tier": "...",
    "hash_bound": true | false
  },
  "binary": { "verdict": "...", "reason": "..." },
  "graded": {
    "verdict": "...",
    "reason": "...",
    "conflict_strength": 0.0-1.0,
    "required_paths": int,
    "available_paths": int
  },
  "useful": bool,
  "regression": bool,
  "null": bool
}
```

## Hard invariants (CI-enforced)

1. The runner is deterministic — two consecutive runs produce
   byte-identical JSON + summary.
2. `evidence/gamma_ledger.json` is **not modified** by this PR.
3. `tools/eai/run_falsifiability_test.py` (PR #195) and
   `tests/eai/calibration/test_falsifiability_v1.py` (NULL_RESULT
   anchor) are **not modified**.
4. `tools/eai/run_graded_falsification_phase_diagram.py` and
   `core/eai/graded_phase_diagram.py` (PR #196) are **not modified**.
5. `core/eai/engine.py` and `core/iev_gate.py` are unchanged
   (production engine untouched).
6. The probe pool is fixed (no per-entry tuning), declared in
   `PROBES` byte-exact.
7. Negative regions (regression / null) are never hidden from the
   summary.

## Outputs (byte-exact paths)

```
artifacts/eai/phase_diagrams/real_gamma_phase_diagram_v1.json
artifacts/eai/phase_diagrams/real_gamma_phase_diagram_v1.csv
artifacts/eai/phase_diagrams/real_gamma_phase_diagram_summary.md
```

## Permitted next moves (after verdict)

- **PHASE_REGION_FOUND on real data** → the STN-analog hypothesis
  is alive on real γ-ledger; v2 PR may propose tightening
  constants with fresh pre-registration; consider DIAGNOSTIC-ONLY
  promotion (not production default).
- **NO_SEPARABLE_REGION_FOUND** → STN-analog is a *grid artifact*
  of PR #196's synthetic templates; archive graded gate as
  diagnostic-only; do NOT pursue further refinement.
- **REGRESSION_REGION_FOUND** → graded gate threatens real
  hash-bound evidence; abandon, preserve as documented null.
- **INVALID_EXPERIMENT** → rebuild; do NOT proceed.

## Claim boundary

> EAI Real-Data γ-Ledger Phase Diagram v1 maps the behavioural
> difference between binary and graded gate configurations across
> 10 real γ-ledger entries × 7 probe-count values × 7
> evidence_path_count values, under a fixed canonical probe pool.
> The diagnostic is read-only on the γ-ledger. No production
> engine is modified. No claim about γ scaling law, brain
> mechanism, or AGI is asserted.

## Forbidden phrasings (binding)

- "real-data phase diagram proves STN architecture"
- "STN-analog validated on γ-ledger"
- "γ scaling confirmed graded-compatible"
- "production-ready STN graded gate"
- "scientific result on real substrates"

Permitted statement form:

> The real-data phase diagram identifies cells where graded
> falsification changes the gate verdict relative to binary on
> the 10 published γ-ledger entries under a canonical probe pool.
> Classification of those cells into useful / regression / null
> regions is reported. No production behaviour changes.

---

**Pre-registered**: 2026-05-14
**Status under CC-META-001 §8.1**: HYPOTHESIS until experiment runs.
