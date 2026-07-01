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

## Deterministic identity

`packet_hash` is a SHA-256 digest over a canonical, key-sorted JSON pre-image of
`(intent, claim_type, error_state, subtasks, raw_input_hash, context_hash)`. It
is a lowercase 64-hex digest, so it satisfies the runtime's retention-hash
contract (Invariant 8 of the EAI spec) and doubles as the reproducible
`artifact_hash`. `raw_input_hash` preserves the **exact original bytes** — two
inputs that differ only in whitespace share a normalized `intent` but keep
distinct provenance and distinct `packet_hash`.

## Hard invariants (enforced by tests)

| Invariant | Enforcement |
|---|---|
| No clarification questions | `emits_clarification` is always `False` |
| No randomness | no RNG in the module |
| No wall-clock dependence | no `time` / `datetime` use |
| No network / hidden mutable state | pure function over frozen dataclasses |
| Frozen dataclasses | `@dataclass(frozen=True)` on every type |
| Stable replay | same `(raw_input, context)` → identical `packet_hash` |
| Deterministic ordering | sub-tasks preserve first-appearance order, de-duplicated |
| Fail-closed | empty input or missing context raises `GateG1CompileError` |
| Bounded decomposition | any non-empty input compiles into ≥ 1 testable sub-task |
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
