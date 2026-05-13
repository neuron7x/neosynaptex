# EAI SPEC V1 — High-Assurance Operational Specification

## 1. Problem (single sentence)
Prevent unverified inference from being promoted into system knowledge while preserving adaptive learning through falsification-governed artifacts.

## 2. Falsifiable hypothesis
If the IEV-gated evidence/kill/quarantine flow with guardrail revalidation is enforced, then false-promotion rate on contradiction traps remains 0, and guardrails evolve through append-only revalidation artifacts rather than direct deletion.

## 3. Invariants (non-negotiable)
1. No evidence without boundary.
2. No promotion without falsification.
3. No integration without artifact.
4. `KILLED` cannot update Integration Memory.
5. `KILLED` may update Guardrail Registry only.
6. Guardrails cannot be deleted directly by evidence.
7. Guardrail state transitions require `RevalidationArtifact`.
8. Retention hashes must be lowercase SHA-256 hex.
9. Emergency-exit mode must fail closed (`QUARANTINED`).

## 4. Contracts
- Claim states: `EVIDENCE | KILLED | QUARANTINED`
- Guardrail states: `ACTIVE | CHALLENGED | SCOPED_DOWN | MERGED | RETIRED | SUPERSEDED | STRENGTHENED`
- Revalidation decisions: `SCOPED_DOWN | RETIRED | SUPERSEDED | STRENGTHENED | UNCHANGED`

## 5. Architecture
- `Evidence -> IntegrationMemory`
- `Killed -> GuardrailRegistry`
- `Quarantined -> OpenQuestionsQueue`
- `Evidence x Guardrail -> RevalidationGate -> RevalidationArtifact -> append-only guardrail state update`

## 6. Semantic revalidation
- Guardrails compile into semantic keys.
- Evidence compiles into semantic keys.
- Registry performs indexed lookup; only matched guardrails enter revalidation.
- Revalidation is fail-closed when ambiguity is unresolved.

## 7. Verification policy
- Software/protocol claims: deterministic local external verification harness (subprocess, exit code, hashes, UTC report).
- Factual/research claims: evidence candidate only; final status still requires full gate decision.

## 8. Metrics (minimum)
- False-promotion rate
- Boundary-violation rate
- Quarantine accuracy
- Overclaim-trap detection
- Guardrail-revalidation throughput

## 9. Required artifacts
- `EvidenceArtifact` / `KillArtifact` / `QuarantinedClaim`
- `GuardrailPatch`
- `InvalidationCondition`
- `RevalidationArtifact`
- `ExternalVerificationReport`
- Ledger append entries

## 10. Governance
Claims of consciousness, AGI proof, universal biological equivalence, or production certification are out of scope for this track.
