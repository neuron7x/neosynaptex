# CLAUDE.md — neosynaptex navigation contract

## Single-source governance anchors
- `invariants.yaml`: global physical and architectural invariants.
- `pyproject.toml`: deterministic dependency and tooling contract.
- `Makefile`: one-command reproducibility entry (`make all`).

## Runtime and science core
- `core/`: canonical computation kernels, invariants, and evidence hardening.
- `contracts/`: interface contracts and schemas.
- `scripts/`: reproducibility, governance gates, and validation tooling.
- `tests/`: executable contract proofs (unit, adversarial, and property tests).

## Reproducibility flow
1. `make init` → install deterministic environment from lock/requirements.
2. `make validate_contracts` → validate invariant contract + traceability.
3. `make test_dynamic` → run property-aware, coverage-gated test matrix.
4. `make all` → fail-closed end-to-end verification pipeline.

## Fail-closed rules
- Silent exceptions are forbidden.
- Any invariant contract parse failure is terminal.
- Missing equation/test trace links are terminal.


## Pull request governance
- Every PR body must include a canonical status line: `claim_status: <label>`.
- Allowed labels: `measured`, `derived`, `hypothesized`, `unverified analogy`, `falsified`.
- Omission or non-canonical labels are fail-closed CI errors (`tools.audit.pr_body_check`).
