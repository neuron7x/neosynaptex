# DNCA × DOPA — Hardening Act H1 (2026-10-16)

**Scope:** `core/eai/dopa_closure_v2.py`, `core/eai/dopa_budget.py`,
`core/eai/dopa_runtime_config.py`, `core/eai/dopa_artifacts.py`,
`configs/dopa_closure_v2/allocator.yaml`, associated security tests.

**Evidence level:** static code inspection and committed regression tests.
**Validation level:** NOT YET LOCALLY EXECUTED; GitHub Actions unavailable/unstable.
**Scientific status:** DOPA-CLOSURE remains UNTESTED.

## First principles

1. **Truth is external to the optimizer.** An internal priority/risk score is not
   a verification event; `verify` creates a request, never `CLOSED`.
2. **No claim can bootstrap its own proof.** Caller-provided booleans in
   `ConstructContext` may permit experimental routing but cannot establish
   instrument validity, verified closure or scientific support.
3. **Compute is finite and numerics are adversarial.** Budget debits cannot
   be negative/nonfinite; extreme exponential penalties must fail closed.
4. **Evidence cannot be silently overwritten.** Reject duplicate claim IDs,
   invalid/escaping `DOPA_RUN_ID`, and collisions on one run directory.
5. **Evidence must bind to the computation that produced it.** Reject configuration
   changes between parsed-byte hashing and archived config snapshot.
6. **Tests are evidence only when executed.** Committed tests and merged PRs
   do not constitute successful test results.

## Risk-reduction ledger (static findings, not a measured incident-rate reduction)

| ID | Original failure mode | Change | Residual risk |
|---|---|---|---|
| C1 / critical | `evidence_risk` threshold emitted `pass` and `CLOSED` without verifier | Removed threshold-only closure. `VERIFY` stays `not_run`. `final_verdict` cannot become `ADMISSIBLE` merely from proxy controls | A qualified independent verifier is still not integrated |
| C2 / critical | One synthetic all-true construct context could be mistaken for instrument qualification | Declare final instrument `INADMISSIBLE` with explicit reasons pending independent verification | `ConstructContext` remains self-attestable for **routing experiments** |
| C3 / high | Negative/NaN/Inf costs or exp overflow could crash or violate reserve invariants | Validate ledger state and costs; extreme exponent makes requested action unaffordable | Still nominal reservations; actual inference and verification costs unmetered |
| C4 / high | `DOPA_RUN_ID` path injection / repeated run ID overwrite / duplicate claims overwrite | Strict single-segment ID, exclusive run-directory creation, duplicate validation before output | Other output roots are trusted caller inputs; no hardened filesystem sandbox |
| C5 / high | YAML `.nan`, underdeclared thresholds/costs; hash/payload race | Recursive finite-number check, required-field/order validation, one-byte read, hash-bound emitted config snapshot | Does not yet bind weights, runtime tensors and data manifest into one signed evidence chain |
| C6 / major | Unverified routing request could be named `closure_artifact.json` | Generate `verification_request.json` and `triage_request.json` with synced SSOT config | Older consumers may depend on legacy filenames; migration needed |

## Important backward-compatibility notice

**Behavioral change:** without an external verifier, the `VERIFY` route no
longer transitions to `CLOSED`; the reported instrument verdict is
`INADMISSIBLE`. This is intentional fail-closed behavior.

**Artifact change:** pending verification writes `verification_request.json`;
pending cheap triage writes `triage_request.json` (old code used
`closure_artifact.json` in both contexts). API consumers must not treat
historical `closure_artifact.json` as an independently verified result.

## Invariants and falsifiers

- I1: for any claim and construct context, `run_allocator_full_path` without an
  external verifier returns no `final_status == CLOSED`; `verification_result`
  remains `not_run`.
- I2: the final instrument verdict cannot be `ADMISSIBLE` in the no-verifier path.
- I3: `0 <= remaining <= envelope`, `spent + remaining == envelope`
  (quantized Decimal). Extreme penalties return overspend/quarantine, not crash.
- I4: a duplicate ID or invalid run path creates no new run artifact.
- I5: same run path cannot be reopened to silently replace past evidence.
- I6: NaN/Inf in YAML and malformed thresholds/costs fail before experiment runs.
- I7: a changed config snapshot cannot retain its previous hash as valid evidence.

Test locations:
- `tests/dopa_closure_v2/test_failclosed_security.py` (new adversarial checks).
- `tests/dopa_closure_v2/test_no_false_closure.py` (strengthened).
- Existing `test_dnca_modulated_router.py`, `test_budget_mode_integrity.py`,
  `test_allocator_full_path.py`, and `test_artifact_uniqueness.py`
  remain required regression coverage.

## Offline execution required before production

```bash
python -m pip install -e '.[dev]' -e agents
python -m pytest -q tests/dopa_closure_v2/
python -m ruff check core/eai/dopa_budget.py core/eai/dopa_runtime_config.py \
  core/eai/dopa_artifacts.py tests/dopa_closure_v2/test_failclosed_security.py
python -m mypy core/eai/dopa_budget.py core/eai/dopa_runtime_config.py
```

Record the exact version, SHA, command, stdout/stderr and exit code. If a
dependency is absent or a test skips, mark that part UNVERIFIED. No CI bypass
is a substitute for execution.

## What cannot yet be claimed

- No validated relationship between DNCA signed valence and verification utility.
- No evidence that neuromodulated routing outperforms non-neural allocators.
- No trusted verifier receipt or externally measured verified-closure rate.
- No complete provenance attestation or cost-inclusive performance evaluation.
- No safety guarantee outside the analyzed call boundaries.

## Promotion rule

`MERGED` does not imply `VALIDATED`. A claim may advance only through
independently reproducible `SOURCE -> CONTRACT -> IMPLEMENTATION -> TEST ->
EXECUTION LOG -> ARTIFACT HASH -> VERDICT`, with no user-supplied Boolean
shortcut, no truth inferred from priority and no promotion on failed or missing
measurements.

**Quintessence:** optimize the allocation of *attention and compute*, never
the definition of *truth*. The verifier, not the generator or controller,
owns evidence-backed closure.
