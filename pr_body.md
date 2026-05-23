### Motivation
Remove sources of nondeterminism and provide a single-command, fail-closed verification path for reproducing bounded cross-substrate γ analyses.

### Description
- Add invariants.yaml as the repository single-source-of-truth for bounded physical and architectural invariants.
- Add CLAUDE.md navigation contract.
- Add equation-to-test traceability through core/testing/governance.py and docs/TRACEABILITY.md.
- Add scripts/validate_invariants.py for invariant/schema/traceability enforcement.
- Harden test/dependency metadata in pyproject.toml.
- Add make all as the fail-closed verification entrypoint.

### Testing
- python3 scripts/validate_invariants.py
- python -m tools.audit.pr_body_check .pr_body.txt
- pytest -q tests/test_gamma_invariant.py

### Claim status
claim_status: derived

Governance and boundary compliance only. No new measured universality, intelligence-law, or validation claim is introduced.
