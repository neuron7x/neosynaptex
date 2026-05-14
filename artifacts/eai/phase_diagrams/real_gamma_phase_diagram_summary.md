# EAI Real-Data γ-Ledger Phase Diagram v1 — Summary

- **schema_version**: `EAI-REAL-GAMMA-PHASE-DIAGRAM-v1`
- **ledger_sha256**: `3f2ed37e86124b1bb43135ce03d111fe35248f9a11fb4c01f3eeaac9863afd67`
- **total_cells**: `490`
- **verdict**: **`NO_SEPARABLE_REGION_FOUND`**
- **verdict_reason**: graded gate produces identical verdicts to binary on every real-ledger cell across the probe-count and evidence-path sweeps; STN-analog is a grid artifact of PR #196 synthetic templates.

## Region totals (global)

| Region | Count |
|---|---:|
| useful | 0 |
| regression | 0 |
| null | 490 |

## Zone breakdown (evidence_tier / ledger_status)

| zone | useful | regression | null |
|---|---:|---:|---:|
| `LOCAL_STRUCTURAL/LOCAL_STRUCTURAL_EVIDENCE_ONLY` | 0 | 0 | 49 |
| `MEASURED_NO_HASH/EVIDENCE_CANDIDATE` | 0 | 0 | 196 |
| `MEASURED_WITH_HASH/EVIDENCE_CANDIDATE` | 0 | 0 | 98 |
| `MEASURED_WITH_HASH/EVIDENCE_CANDIDATE_NULL_FAILED` | 0 | 0 | 98 |
| `NUMERICAL_INTERNAL/EVIDENCE_CANDIDATE` | 0 | 0 | 49 |

## Claim boundary

> EAI Real-Data γ-Ledger Phase Diagram v1 reports binary-vs-graded
> gate behaviour across 10 real γ-ledger entries × 7 probe-count
> values × 7 evidence-path-count values, under a fixed canonical
> probe pool. Diagnostic only. γ-ledger read-only. No production
> engine modified.
