# CIP-01 · Utility and Dual-Process Synthesis

claim_status: derived

## Status

- **Protocol ID:** `CIP-01-NEDP`
- **Parent protocols:** `CIP-01`, `DIM-01`, `NEOSYNAPTEX-PROTOCOL-v1.1`
- **Status:** PROPOSED / INTEGRATION-READY
- **Scope:** defines the value layer that converts noisy candidate input into bounded research-engineering artifacts.
- **Non-claim:** neuroeconomic, dual-process, and free-energy language is used as an operational analogy only. This document does not claim biological identity with human cognition or formal proof of the Free Energy Principle.

---

## 1. Thesis

`CIP-01` is not information accumulation. It is a value-filtering mechanism.

```text
external signal → candidate mutation → utility scoring → invariant filtering → verification → artifact or pruning
```

The system treats external chaos as raw candidate material. A candidate becomes valuable only when it can be expressed as a falsifiable, traceable, and verifiable artifact.

---

## 2. Utility Function

Let `pi` be a candidate transformation path from captured input to artifact.

```math
U(pi) = E_pi[R] - lambda H(pi) - mu C(pi)
```

Where:

- `R` is protocol reward: correctness, invariant satisfaction, traceability, and artifact usefulness.
- `H(pi)` is retained uncertainty or noise.
- `C(pi)` is cognitive, compute, review, or process cost.
- `lambda` controls entropy aversion.
- `mu` controls process-cost aversion.

Boundary: increasing `lambda` does not create truth and does not make the system fully deterministic. It makes acceptance more conservative by penalizing uncertainty. Useful uncertain candidates should enter `QUARANTINE`, not silent rejection.

---

## 3. Dual-Process Architecture

| Layer | Role | Output | Gate |
| --- | --- | --- | --- |
| System 1 | stochastic generation | candidates | schema and hypothesis extraction |
| System 2 | invariant monitor | decisions | verifier, CI, human gate |

System 1 expands the search space. System 2 filters and accepts only candidates that satisfy the protocol.

```text
candidate → schema gate → invariant gate → utility score → external verifier → ACCEPT | QUARANTINE | REJECT | ENTROPY
```

LLM output is candidate inference, not authority.

---

## 4. Logical Selection Rule

Let `Omega` be the candidate space, `Phi` the invariant predicate, and `D(x, target)` the semantic distance from operator intent.

```math
x* = argmin_{x in Omega} [D(x,target) + alpha C(x) + beta H(x) + M * 1[not Phi(x)]]
```

For BLOCKER invariants, `M` is effectively infinite. Therefore invalid candidates are not selectable:

```math
Omega_valid = {x in Omega | Phi(x)=1}
```

```math
x* = argmin_{x in Omega_valid} [D(x,target) + alpha C(x) + beta H(x)]
```

If `Omega_valid` is empty, the system must return `NO_ACCEPTED_ARTIFACT` or `QUARANTINE`; it must not select the least-bad invalid candidate.

Boundary: this selects the best accepted candidate under declared constraints. It does not prove global truth.

---

## 5. Cognitive Compression Algorithm

```python
def cognitive_inference(raw_data, intent, constraints):
    candidates = system1_generate(raw_data, intent)
    admitted = []

    for candidate in candidates:
        if not has_falsification_boundary(candidate):
            mark(candidate, "ENTROPY", reason="missing_falsification")
            continue

        if not satisfies_schema(candidate, constraints.schema):
            mark(candidate, "REJECT", reason="schema_violation")
            continue

        if not satisfies_invariants(candidate, constraints.invariants):
            mark(candidate, "REJECT", reason="invariant_violation")
            continue

        utility = reward(candidate) - constraints.lambda_entropy * entropy(candidate) - constraints.mu_cost * cost(candidate)
        admitted.append((utility, candidate))

    if not admitted:
        return "NO_ACCEPTED_ARTIFACT"

    best = deterministic_tie_break(max_by_utility(admitted))
    return external_verify_or_quarantine(best)
```

This algorithm separates three operations that must not be collapsed:

1. **Generation:** proposes candidates.
2. **Selection:** ranks only valid candidates.
3. **Promotion:** requires verifier or quarantine state.

---

## 6. Invariants

```yaml
invariants:
  - id: CIP-01-NEDP-01
    metric: utility_function_defined
    pass_condition: reward, entropy_penalty, and cost_penalty are declared

  - id: CIP-01-NEDP-02
    metric: generation_selection_promotion_separation
    pass_condition: candidate generation is separated from utility selection and artifact promotion

  - id: CIP-01-NEDP-03
    metric: hard_constraint_priority
    pass_condition: BLOCKER violations cannot be selected by utility optimization

  - id: CIP-01-NEDP-04
    metric: uncertainty_quarantine
    pass_condition: useful uncertain candidates are quarantined before promotion

  - id: CIP-01-NEDP-05
    metric: deterministic_acceptance_boundary
    pass_condition: accepted artifacts pass fixed gates, tie-break rules, and external verifier status
```

---

## 7. Validation Plan

### Positive case

Accepted candidates must have:

- falsification boundary;
- protocol mapping;
- utility score;
- invariant pass;
- provenance;
- verifier or quarantine decision;
- integration target.

### Negative controls

Reject or quarantine:

- novelty with no test path;
- high salience with no artifact destination;
- low-cost candidate that violates invariants;
- high-reward candidate with missing provenance;
- model agreement with no external verifier;
- empty valid candidate set.

---

## 8. Operating Doctrine

```text
signal is cheap
validated artifact is expensive
unverified novelty is liability
traceable falsification is value
```

`CIP-01-NEDP` does not reward volume. It rewards verified closure.

```text
No gate, no artifact. No falsification, no promotion. No provenance, no trust. No CI trace, no merge.
```
