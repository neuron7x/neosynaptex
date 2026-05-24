# DOPA-CLOSURE v2 CI Repair Act

claim_status: derived

## Scope

This act records the current closure state for PR #205 after Codex interruption.

## Verified CI state

- Security: success.
- protocol-ci: success.
- NFI CI Type Check: success.
- NFI CI Lint & Format: failed.

## Active root cause

The only active blocker observed in the latest NFI CI log is Ruff I001 in:

`tests/dopa_closure_v2/test_budget_conservation.py`

Required import order:

```python
from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal
```

## Boundary

This is a style/import-order blocker, not an allocator logic, security, type-system, schema, or protocol failure.

## Next gate

After applying the import-order patch, rerun NFI CI. If NFI CI passes, the PR should be treated as integration-ready for the experimental allocator boundary, not mission-critical production.
