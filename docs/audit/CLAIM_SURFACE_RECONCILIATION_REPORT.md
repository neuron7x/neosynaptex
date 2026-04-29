# Claim Surface Reconciliation Report — Phase 2 (RECONCILED)

> **Verdict at PR head:** `RECONCILED` — 0 contradictions detected.
>
> **Phase 1 baseline (PR #158):** 48 contradictions across the ledger,
> README, and BN-Syn surface.
>
> **Phase 2 outcome (this PR):** all 48 contradictions resolved through
> honest downgrades (no fabricated hashes, no invented rerun commands).
> The reconciliation gate now exits 0 on the canonical repository state.

The full machine-readable JSON and the always-regenerable markdown
listing are produced by:

```bash
python -m tools.audit.claim_surface_reconciliation \
    --report docs/audit/CLAIM_SURFACE_RECONCILIATION_REPORT.md \
    --json-out evidence/claim_surface_reconciliation.json
```

Re-running the tool overwrites this file with the current contradiction
set. Any drift from `RECONCILED` must be explained in a follow-up PR.

## Resolution summary (Phase 1 → Phase 2)

| Phase 1 contradiction code | count | resolution |
|---|---|---|
| `VALIDATED_WITHOUT_DATA_SHA256` (CRITICAL) | 9 | downgrade or populate with real hash where evidence exists; `data_sha256` field added to schema |
| `VALIDATED_WITHOUT_ADAPTER_CODE_HASH` (CRITICAL) | 7 | downgrade or populate with real hash; 3 substrates retain real adapter hashes |
| `VALIDATED_WITHOUT_NULL_FAMILY_STATUS` (HIGH) | 10 | `null_family_status` field added to schema; populated where surrogate evidence exists |
| `VALIDATED_WITHOUT_RERUN_COMMAND` (HIGH) | 10 | `rerun_command` field added; populated only for `lemma_1_kuramoto_dense` (real entry-point) |
| `VALIDATED_WITHOUT_CLAIM_BOUNDARY_REF` (HIGH) | 10 | `claim_boundary_ref` field added; per-substrate ref to `docs/CLAIM_BOUNDARY.md` claim row or BN-Syn boundary doc |
| `BNSYN_OVERCLAIM` (CRITICAL) | 1 | `bnsyn` downgraded to `LOCAL_STRUCTURAL_EVIDENCE_ONLY` with `downgrade_reason="KAPPA_NOT_GAMMA"`; `gamma`/`ci_*` set to `null` (no κ-as-γ projection) |
| `README_VALIDATED_COUNT_INCONSISTENT_WITH_EMPTY_CORE` (HIGH) | 1 | `README.md` lines 82 & 196 reworded to "measured candidate substrates" with explicit §5.1 reference |

Total: **48 → 0**.

## Phase 2 ledger downgrade ledger

Per `evidence/gamma_ledger.json#downgrade_log[0].downgrades`:

| substrate | from → to | reason |
|---|---|---|
| `zebrafish_wt` | VALIDATED → EVIDENCE_CANDIDATE | NO_REAL_DATA_HASH |
| `gray_scott` | VALIDATED → EVIDENCE_CANDIDATE | NO_REAL_DATA_HASH |
| `kuramoto` | VALIDATED → EVIDENCE_CANDIDATE | NO_REAL_DATA_HASH |
| `bnsyn` | VALIDATED → **LOCAL_STRUCTURAL_EVIDENCE_ONLY** | **KAPPA_NOT_GAMMA** |
| `eeg_physionet` | VALIDATED → EVIDENCE_CANDIDATE | NO_EXTERNAL_REPLICATION |
| `hrv_physionet` | VALIDATED → EVIDENCE_CANDIDATE | NO_REAL_DATA_HASH |
| `eeg_resting` | VALIDATED → EVIDENCE_CANDIDATE | NO_EXTERNAL_REPLICATION |
| `serotonergic_kuramoto` | VALIDATED → EVIDENCE_CANDIDATE | NO_EXTERNAL_REPLICATION |
| `hrv_fantasia` | VALIDATED → EVIDENCE_CANDIDATE | NO_EXTERNAL_REPLICATION |
| `lemma_1_kuramoto_dense` | VALIDATED → EVIDENCE_CANDIDATE | NO_EXTERNAL_RERUN |

All 10 entries downgraded; the canon now matches `CLAIM_BOUNDARY.md §5.1`
("evidential core empty"). No entry was promoted; no hash was fabricated;
no rerun command was invented.

## Schema enforcement (new in Phase 2)

`evidence/ledger_schema.py` exposes:

- `LedgerEntry` — frozen, slot-only dataclass with `__post_init__`
  validation. Constructing a `LedgerEntry` with VALIDATED status but
  null evidence fields raises `LedgerSchemaError`.
- `validate_ledger(ledger)` — returns a per-substrate map of schema
  violations. Empty dict ↔ ledger is canon-clean.
- `CANONICAL_LADDER`, `ALLOWED_DOWNGRADE_REASONS`, `ALLOWED_EVIDENCE_TIERS`
  — single source of truth for ladder states, reason codes, and evidence
  tiers. All three are referenced by:
  - `tools/audit/claim_surface_reconciliation.py` (Phase 1 gate)
  - `tools/audit/gamma_ledger_integrity.py` (CI workflow gate)
  - `tests/test_ledger_schema.py` (16 schema-invariant tests)

## How to re-promote a substrate to VALIDATED

A downgrade can only be lifted by closing all six `CLAIM_BOUNDARY.md §5.1`
gates AND populating the schema fields:

1. Public bundle exists (downloadable by an arbitrary third party).
2. Pipeline is deterministic and passes `tools/audit/adapter_scope_check.py`.
3. At least one preregistered analysis filed on OSF.
4. γ reproduced from raw data under the frozen pipeline (real `data_sha256`
   in the ledger).
5. At least one surrogate family from `NULL_MODEL_HIERARCHY.md` did NOT
   reproduce the observed γ (real `null_family_status`).
6. At least one external rerun committed to
   `evidence/replications/registry.yaml` with a real `commit_sha`
   (matching `rerun_command`).

Re-promotion = a PR that:

- Cites the substrate's current `downgrade_reason`.
- Names the `CLAIM_BOUNDARY.md §5.1` gate the new evidence closes.
- Populates the schema field that was previously null.
- Sets `status` back to `VALIDATED` (or higher) and removes
  `downgrade_reason`.

The reconciliation gate is the first reviewer: a re-promotion that
leaves any required field null fails fast with
`VALIDATED_WITHOUT_*` or `DOWNGRADE_WITHOUT_REASON`.

## What this report does NOT do

- Does not auto-promote any entry.
- Does not auto-modify the ledger.
- Does not silently downgrade — every status change is in the
  `downgrade_log` with date, actor, audit source, and reason.
- Does not replace Phase 3 (Null Screen) / Phase 4 (Negative Substrate)
  / Phase 5 (Meta-Analysis) / Phase 6 (Replication Packs) gates.

## Invariants preserved

- κ ≠ γ — `bnsyn` no longer carries a γ value (`null` in ledger v2.0.0).
- Four-state ladder canonical (extended with documented sub-VALIDATED
  states; not promoted above VALIDATED).
- `BLOCKED_BY_METHOD_DEFINITION` reserved for the mycelium contract.
- Strict-JSON output (`allow_nan=False`).
- No claim promotion. No hash fabrication. No rerun-command invention.
