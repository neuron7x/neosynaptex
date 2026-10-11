# Branch recovery — evidence-checked decisions, pass 2

**Date:** 2026-10-11  
**Snapshot:** original 81 refs, `main@181353a73ab6c24deeb4d1ec6137683ae33d038c`.  
**Safety:** no historical branch deleted, force-pushed or merged. Main unchanged.

## Decisions supported by exact blob parity

### `sincerity/pass-1-downgrade-overclaims` — NO MERGE (already on main)

All three files changed by this historical branch have **identical Git blob SHAs** in current `main`:
- `CANONICAL_POSITION.md` — `f7d98d095df8930c1f4fa8e96b1fb36d452d2fdb`;
- `evidence/IMMACULATE_REPORT.md` — `08720ff20a35bbc517df80809ef2372c6af14009`;
- `evidence/replications/physionet_chf2db_contrast/REPLICATION_REPORT_HRV_PATHOLOGY_CONTRAST.md` — `8621c685eb0fc6e9cb42439a2eb92dcff2710b23`.

Decision: content already incorporated (ancestry may differ due cherry-pick/squash). Do not merge again. Retain branch until archive-policy review.

### HRV `results/full_cohort_null` subset of `feat/neurophase-run1-pipeline` — NO MERGE (duplicate evidence)

In the branch there are 38 `results/full_cohort_null/<record>/null_suite.json` and one `null_suite_summary.json`. All **38** per-record result Git blob SHAs equal corresponding `main:evidence/surrogates/<record>/null_suite.json`. The summary equals `main:evidence/surrogates/null_suite_summary.json`, blob `64902a95ea0cc29c31d06254af36cc1fcfabeb97`. Branch result tree duplicates already-committed evidence.

The summary records `n_subjects=69`, `split_scope=development_only`, `68 SEPARABLE`, `1 BORDERLINE`. These are descriptive outputs, **not independent validation**. No second copy needed.

### M-invariant / M2 sibling work — CONSOLIDATED INTO DRAFT PR #3

Source: `feat/neurophase-run1-pipeline` composite. Exact blob parity confirmed for representative unique artifacts of:
- `feat/m-invariant-mfn-bnsyn-bridge` — experiment script;
- `feat/m2-1-status-freeze` — claim registry, report;
- `feat/m2-2-scale-diagnostics` — diagnostic script, README;
- `feat/m2-3-bnsyn-spatial-embedding` — design note;
- `feat/m2-4-scale-invariant-operators` — design note;
- `feat/m2-5-pre-registration` — locked contract.

Seventeen selected source blobs copied to independent review branch with base `main`; draft: https://github.com/neuron7x/neosynaptex/pull/3.
Excluded unrelated code and all synthetic EEG and duplicate HRV outputs.

**Negative science:** `results/m_invariant_bridge/run_v1.json` = `INVALID_HWI`; `results/m_invariant_scale_diagnostics/run_v1.json` = `INVALID_OPERATOR`; registry `OPEN_NARROWED`. This falsifies the specified value-axis operator for the stated contract, not the entire research hypothesis. **No merge until tests and evidence hash reproduction.**

## High-severity merge blockers

### `feat/neurophase-run1-pipeline` — DO NOT MERGE WHOLE COMPOSITE

Graph: 12 ahead, zero behind, 123 changed files; includes M2, 38 duplicate HRV result records, security changes, and EEG RUN1.

EEG ledger and feature manifest show a **four-subject synthetic self-test** at `/tmp/synth_ds`, not an execution of OpenNeuro ds003474 raw EEG. In that self-test: H1 `REJECTED` (p=0.3910022), H2 `REJECTED` (p=0.1218379), ceiling `EEG_TRACK_CLOSED`. Source generator claims planted θ-phase/behavior coupling in positive controls, but aggregate H1 did not pass. Treat this as an unresolved **positive-control sensitivity/power check** — it does not scientifically reject the real-world hypothesis. Reconcile protocol and evidence; do not call self-test a real-data EEG result.

Action: future independent EEG-only extraction must exclude synthetic logs/binary artifacts and add an explicit positive-control detection power acceptance gate before any empirical promotion.

### `security/codeql-debt-resolution` / `sec/codeql-followup-hmac-revert` — BLOCK DIRECT MERGE

Current main does not contain identical versions of several affected security source files. However:
- Initial `_validated_path` denies `..` then `Path.resolve()`; alone this **does not constrain absolute paths, symlinks or allowed roots** against adversarial path input.
- Initial RBAC `MLSDM_API_KEY_PEPPER` has hardcoded default. This is not fail-closed for production secrets and is unsuitable as a general secure key storage guarantee.
- Follow-up explicitly reverts `.resolve()` and narrows the threat model to operator-controlled configuration, saying CodeQL flows were dismissed as not exploitable. This must be evaluated against actual caller trust boundaries.
- Subsequent dependency patch `sec/dependabot-pyo3-postcss` carries 2026-04-30 pins; do not accept old pins without current vulnerability and build validation.

Action: author a new narrowly scoped security PR after threat-model audit; test path traversal (including absolute paths, symlinks, non-existent targets), key-pepper configuration and upgrade matrix. No current security proof or live CI is recorded.

### `ci/canonical-admissibility-split-slow` — HOLD

Moves computationally expensive canonical estimators off push and onto manual `workflow_dispatch`. Can reduce CI time, but **canonical scientific gate may silently stop executing** unless a scheduled/required evidence job replaces it. Review coverage first.

### `ci/hrv-real-data-scheduled` — HOLD

Adds scheduled non-blocking network-dependent PhysioNet check; it is not an execution record. GitHub API currently returned zero Actions runs/statuses and repository Issues are disabled. Inspect fallback reporting behavior before accepting.

### Phase 3 and archival docs — SELECTIVE RECOVERY

For `feat/phase-3-null-screen`, `.github/workflows/phase_3_null_screen.yml` and `docs/audit/PHASE_3_PROTOCOL.md` are byte-identical to main; `tools/phase_3/run_null_screen.py` differs, so **do not** mark whole branch merged. Phase 4 and old XFORM drafts require Phase 4b claim compatibility.

## Implemented review changes
- Draft PR #1: full initial 81-ref ledger and audit gates, https://github.com/neuron7x/neosynaptex/pull/1
- Draft PR #2: README claim-boundary, legacy-method and CI representation fixes, https://github.com/neuron7x/neosynaptex/pull/2
- Draft PR #3: curated M2 17-blob scientific extraction, https://github.com/neuron7x/neosynaptex/pull/3

## Remaining verification boundary

No local runnable clone/network-dependent datasets were accessible for test execution in this environment. Actions runs/statuses could not be verified. Draft PRs are **not merge approvals**. Remaining branch dispositions in the 81-ref ledger are conservative holds pending complete code/evidence parity and executable validation.

## Additional branch parity results

- `feat/expelliarmus`: `core/expelliarmus.py` exactly matches `main`; verify all remaining files before archive.
- `feat/intelligence-certificate`: `core/intelligence_certificate.py` matches `main`.
- `feat/mathematical-precision`: `core/mathematical_precision.py` matches `main`.
- `feat/measurement-contract-verifier`: `tools/adversarial/verifier.py` matches `main`.
- `feat/evidence-hardening`, `feat/architecture-aesthetics` and `feat/gamma-ledger-integrity`: sampled core/audit files have different blob SHAs from `main`, requiring hunk-level review rather than blanket merge.
- `feat/gamma-program-toolchain-freeze`: `STACK.lock` is absent from `main`; a 2026-04 pinned toolchain snapshot exists on this historical branch, but needs current dependency validation.
- `feat/gamma-program-sampen-null-suite`: 9,780 branch blobs versus 10,009 in main. Of branch blob paths, 9,409 are identical, 139 differ and 232 exist only on branch; current main has 461 other paths absent from this branch. Branch-only files include outdated manuscripts, outlier protocols, old claim workflows and `STACK.lock`. Recover scientifically valid unique evidence selectively; direct bulk merge is blocked.
