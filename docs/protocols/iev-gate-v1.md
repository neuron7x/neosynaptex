# IEV-Gate v1

## Purpose
Define a fail-closed promotion gate where no inference becomes integrated knowledge without verified closure.

## Decision mapping
- `PASS` → `EVIDENCE`
- `FAIL` → `KILLED`
- `INSUFFICIENT_TESTABILITY` → `QUARANTINED`

## Verified-closure rule
A claim may be promoted to `EVIDENCE` only when all required gates pass:
1. schema validity,
2. explicit purpose,
3. claim-type declaration,
4. evidence mapping,
5. provenance,
6. null/surrogate controls,
7. falsifier conditions,
8. external verification,
9. reproducibility manifest,
10. security checks,
11. robustness checks,
12. boundary declaration,
13. retention hashing,
14. CI/regression checks,
15. integration authorization.

If any gate fails or is missing, the decision is `KILLED` or `QUARANTINED` (never `EVIDENCE`).

## Operational fail-closed controls
- **Emergency exit**: if `EAI_EMERGENCY_EXIT` is enabled, the gate returns `QUARANTINED` regardless of other signals.
- **Invalid retention hash**: non-SHA-256 retention hashes force `QUARANTINED`.
- **Failed falsification**: explicit falsification failure forces `KILLED`.

## Auditability requirements
Every decision must emit an auditable trail with:
- UTC timestamp,
- claim ID,
- decision status,
- retention hash,
- verification/revalidation evidence references.
