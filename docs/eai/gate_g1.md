# Cognitive Compiler Gate G1 — ingress layer for the EAI runtime

`claim_status: derived`

## What it is

Gate G1 is the **ingress compiler** that sits *before* the existing EAI runtime
(`core/eai/engine.py::EAIEngine`: falsification engine → IEV gate → artifact
ledger → integration memory). It compiles raw, chaotic, fatigued or
out-of-distribution human input (Variant A) into a deterministic
`ExecutionPacket` (Variant B) that seeds the structured inputs the runtime
already consumes.

Gate G1 is a **compiler, not an oracle**. It removes the runtime's dependence on
a *clear* user state: when the input is noisy or aggressive, the gate does not
ask clarifying questions — it compiles the signal into a bounded, testable work
package. Whether the seeded claim is then promoted, killed or quarantined is
decided **downstream** by the falsification and IEV gates, never by Gate G1.

## Where it lives

- Module: `core/eai/gate_g1.py`
- Public API re-exported from `core/eai/__init__.py`
- Tests: `tests/eai/integration/test_gate_g1.py`

## Pipeline

```text
raw chaotic input
  → GateG1Context (known environment / project / repository / constraints)
  → compile_execution_packet(raw_input, context)
  → ExecutionPacket
       ├─ to_claim_card()        → ClaimCard        ┐
       ├─ to_boundary_card()     → BoundaryCard     │  seeds
       ├─ to_reproducibility()   → ReproducibilityManifest
       └─ retention_hash()       → SHA-256 (== packet_hash)
  → EAIEngine.run_candidate(...)          (EXISTING verified runtime)
  → EVIDENCE | KILLED | QUARANTINED
```

## Identity model — semantic vs provenance

Two orthogonal hashes:

- **`packet_hash`** — the *semantic replay identity*. SHA-256 over a canonical,
  key-sorted, **schema-versioned** JSON pre-image of
  `(schema_version, intent, claim_type, error_state, subtasks, context_hash)`.
  The compiled `intent` is whitespace-collapsed and **Unicode NFC**-normalized,
  so byte-different encodings of the same request (extra spaces, NFC vs NFD
  accents) map to **one** `packet_hash` — they are the same unit of work. It is
  a lowercase 64-hex digest, satisfying the runtime retention-hash contract
  (EAI spec Invariant 8) and doubling as the reproducible `artifact_hash`.
  `schema_version` is bound into the pre-image, so a future compiler revision
  yields a distinct identity for the same input (no cross-version aliasing).
- **`raw_input_hash`** — the *exact-byte provenance*. SHA-256 of the original
  input verbatim; it distinguishes encodings that `packet_hash` intentionally
  unifies. It is **not** part of the replay identity.

## Hard invariants (enforced by example + property tests)

| Invariant | Enforcement |
|---|---|
| No clarification questions | `emits_clarification` is always `False` |
| No randomness / wall-clock / network | pure function; no `random` / `time` / I/O |
| No hidden mutable state | every dataclass is `frozen=True, slots=True` |
| Stable replay | same `(raw_input, context)` → identical packet (property test) |
| Semantic identity | whitespace/NFC variants share one `packet_hash` (property test) |
| Deterministic ordering | sub-tasks preserve first-appearance order, de-duplicated |
| Bounded work | `1 ≤ len(subtasks) ≤ 256`; input capped at 20 000 chars |
| Fail-closed | empty / non-`str` / over-length input or missing context raises `GateG1CompileError` — no silent truncation |
| No fabricated evidence | `to_boundary_card().tested_conditions == []` (the compiler tested nothing) |
| Claim boundary preserved | `failure_boundary` forbids scientific/consciousness claims |

## Usage

```python
from core.eai import GateG1Context, compile_execution_packet
from core.eai.engine import EAIEngine

ctx = GateG1Context(
    environment="linux-ci",
    project="neosynaptex",
    repository="neuron7xLab/neosynaptex",
    constraints=("no network", "deterministic only"),
)
packet = compile_execution_packet("everything is broken JUST MAKE IT WORK", ctx)

outcome = EAIEngine().run_candidate(
    claim=packet.to_claim_card(),
    boundary=packet.to_boundary_card(),
    contradiction_markers=[],
    reproducibility=packet.to_reproducibility(environment=ctx.environment),
    retention_hash=packet.retention_hash(),
    revalidation_passed=True,
    integration_patch={"guardrail_update": True},
    next_intent_delta={"delta": 1},
)
```

## Scope boundary (governance)

Gate G1 makes **no** claims of consciousness, AGI, biological equivalence or
production certification. It performs a purely engineering transition —
unstructured signal → structured protocol — and hands off to the existing
verified runtime, which it does not replace.
