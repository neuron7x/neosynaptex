# DNCA × DOPA — Independent Verification Receipt Protocol v1

**Status:** experimental proof boundary for **exact bounded integer arithmetic only**. No general truthfulness, model-safety or cognitive-efficiency claim. Existing DOPA-CLOSURE theory remains **UNTESTED**.

> **Attestation extension (2026-10-16):** This original protocol is still
> valid for its **UNATTESTED** receipt mode. The new optional
> `attestation_key` argument adds HMAC-authenticated routing archive
> provenance, and its trust assumptions are specified in
> [DNCA × DOPA Attestation Trust Boundary](DNCA_DOPA_ATTESTATION_TRUST_BOUNDARY.md).
> A successfully authenticated archive does not establish factual
> truthfulness beyond the exact-integer domain or a valid NeuroAI experiment.

## Fundamental trust principle

An agent's internal reward, prediction error, novelty, certainty and budget-priority values may select **which** proposition to check. They do not establish the proposition's **truth**. An independent verifier must evaluate the proposition from its original committed content, without reading those values.

**Three separate outputs:** routing request (not truth), domain-specific verification receipt (narrow mathematical truth), and scientific performance claim (requires externally measured comparative experiments).

## Implemented boundary

- `core/eai/dopa_independent_verifier.py`: pure, deterministic exact integer computation; only `add`, `subtract` and `multiply` with bounded operands and no `eval`, network, subprocesses, LLM calls or numerical tolerance.
- `ArithmeticClaim` includes ID, operation, operands, asserted result.
- `arithmetic_commitment(claim)` is SHA-256 over canonical JSON of the exact assertion and an explicit domain tag.
- `run_allocator_full_path(..., claim_commitments={id: sha256})` validates complete keys and digest shape **before creating a run directory** and embeds the commitments in the routes.
- `verify_scheduled_arithmetic(run_dir, claim)` independently recomputes, checks input commitment, archived route/final-report equivalence, route eligibility, pending status and nominal budget availability.
- `verification_receipt.json` is published atomically with an exclusive filesystem hard link; an existing receipt cannot be silently overwritten.
- Neither old route nor original `final_verdict.json` is modified. Overall instrument status remains **INADMISSIBLE** even if the bounded arithmetic claim receives a valid `VERIFIED` receipt.

## Full-path example (repository root)

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_independent_verifier import (
    ArithmeticClaim, arithmetic_commitment, verify_scheduled_arithmetic,
)
from core.eai.dopa_types import ClaimSignal
from core.eai.dopa_result import Ok

case = ArithmeticClaim("proof-1", "multiply", 7, 9, 63)
signals = ClaimSignal("proof-1", 0.6, 0.7, 0.6, 0.1, 0.8, 0.55)
# These flags are a synthetic experiment fixture, NOT independent attestation.
gate = ConstructContext(True, True, False, False, True, True)

with TemporaryDirectory() as output:
    result = run_allocator_full_path(
        "configs/dopa_closure_v2/allocator.yaml", [signals], output, gate,
        claim_commitments={case.claim_id: arithmetic_commitment(case)},
    )
    assert isinstance(result, Ok)
    run = Path(output) / "runs" / result.value["run_id"]
    receipt = verify_scheduled_arithmetic(run, case)
    assert receipt["verdict"] == "VERIFIED"
    assert result.value["final_verdict"] == "INADMISSIBLE"
```

## Formal definitions and admissibility

Define `C` as a well-formed arithmetic assertion, `H` as SHA-256 and `J(C)` as the canonical JSON encoding of `{"domain": "dopa.arithmetic.v1", "claim": C}`. The declared content commitment is `h=H(J(C))`.

The independent verdict is permitted only after all preconditions hold:

1. **Payload binding:** the route's stored digest is exactly `H(J(C))`, including the asserted answer, not merely a matching claim ID.
2. **Archive consistency:** the independently read per-claim route equals the corresponding route in the archived final report, and config hashes agree.
3. **Eligible request:** route action is `verify` or `escalate`, status is pending, no previous verifier-result field indicates execution, and no budget overspend/unmet need is recorded.
4. **Namespace and integrity:** strict bounded arithmetic domain; safe IDs; duplicate JSON keys, nonfinite JSON constants, symlinked critical inputs and oversized JSON are rejected.
5. **Non-replacement:** atomic exclusive receipt creation; replay to the same path is rejected.
6. **Exact oracle:** `computed = left (+, -, ×) right` using native exact integers; `VERIFIED ⇔ computed == asserted`. Incorrect assertions receive `REFUTED`.
7. **Scientific separation:** a receipt cannot change global model, DNCA or verification-instrument admissibility.

**Conditional correctness:** Given an uncompromised interpreter/verifier and well-typed bounded integers, the three supported integer operations yield exact results; therefore the verifier's verdict is correct *within that domain*. It neither proves upstream inputs authentic nor proves arbitrary prose true.

## Residual attack and assurance gaps

A SHA-256 digest is a content commitment, **not** a digital signature. An adversary who can rewrite all run artifacts and hashes may forge an internally consistent archive. Atomic no-overwrite protects against ordinary accidental/replayed writes, not a hostile actor who can delete files or control the filesystem. Harden using external immutable logging, independent signing keys, signed input manifests and reproducible verifier-code identity before claiming non-repudiation. Nominal route budget is not metered CPU/GPU cost. The signed DA signal's predictive utility remains unvalidated, and the caller-provided `ConstructContext` does not constitute independent instrument certification.

The test is intentionally narrow: it measures whether the epistemic authority boundary is constructible without a language model's cooperation. It does **not** demonstrate intelligent improvement.

## Reproduction

```bash
python -m pytest -q tests/dopa_closure_v2/test_independent_arithmetic_verifier.py
python -m pytest -q tests/dopa_closure_v2/test_independent_arithmetic_full_path.py
python -m pytest -q tests/dopa_closure_v2/
python -m ruff check core/eai/dopa_independent_verifier.py tests/dopa_closure_v2/test_independent_arithmetic_verifier.py tests/dopa_closure_v2/test_independent_arithmetic_full_path.py
```

**Execution evidence:** 19/19 isolated verifier tests passed locally on Python 3.13.5 / pytest 9.0.2 without GitHub Actions. The **actual repository full-path integration tests have not been executed** in that environment. The machine lacked network resolution for GitHub, so source was committed through the connected GitHub integration rather than cloned locally.

**Promotion rule:** do not report superior NeuroAI reasoning until domain-qualified independent verifiers, real DNCA signals, end-to-end *measured* compute budgets, preregistered baselines and external reproducibility independently pass.

**⊛ Quintessence:** Intelligence may propose and prioritize. Only an independent domain-valid computation can verify. A verifier's mathematical scope must never be mistaken for the model's epistemic reliability.
