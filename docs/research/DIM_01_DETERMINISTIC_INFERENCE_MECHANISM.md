# DIM-01 · Deterministic Inference Mechanism

claim_status: derived

## Status

- **Protocol ID:** `DIM-01`
- **Parent protocol:** `CIP-01`
- **Status:** PROPOSED / INTEGRATION-READY
- **Scope:** formalizes how stochastic LLM candidate generation is converted into a deterministic acceptance policy through constrained decoding, invariant gates, and external verification.
- **Non-claim:** `DIM-01` does not claim that the LLM itself becomes ontologically deterministic or truth-preserving. It defines a deterministic **selection and acceptance mechanism** over candidate outputs.

---

## 1. Objects

Let `(Ω, F, P)` be a probability space representing stochastic generation traces. Let `X` be the token alphabet and `X*` the finite sequence space.

For model parameters `θ`, the generator defines a conditional next-token distribution:

```math
P_\theta(x_t \mid x_{<t}) : X^* \times X \to [0,1]
```

For a prefix `h = x_<t`, the local entropy is:

```math
H_\theta(h) = -\sum_{x \in X} P_\theta(x \mid h) \log P_\theta(x \mid h)
```

Boundary: `H_θ(h)` may be zero or positive depending on the prefix, backend, masking, and model distribution. In this protocol, “chaos” means candidate-space uncertainty, not a physical entropy claim.

---

## 2. Constraint System

Let `G` be a grammar/FSM/schema defining syntactic admissibility. Let `Φ_prefix` be the set of prefix-checkable invariants and `Φ_global` the set of full-sequence invariants.

The admissible next-token set at step `t` is:

```math
C_t(h) = \{x \in X \mid Valid_G(h \circ x) \land \forall \phi \in \Phi_{prefix},\; \phi(h \circ x)=1\}
```

Where:

- `Valid_G` returns whether the candidate prefix remains grammar/schema/FSM compliant.
- `Φ_prefix` includes constraints that can be evaluated during decoding.
- `Φ_global` includes constraints that require a complete candidate sequence, such as cross-field consistency, artifact linkage, or external audit reports.

This separation prevents a fake proof where full-document properties are incorrectly claimed to be checked at every token.

---

## 3. Masked Projection

For `C_t(h) ≠ ∅`, define the live admissible set:

```math
A_t(h) = \{x \in C_t(h) \mid P_\theta(x \mid h) > 0\}
```

If `A_t(h) = ∅`, the transition must fail closed because no admissible token has model support.

For `A_t(h) ≠ ∅`, define the masked distribution:

```math
Q_{\theta,\tau}(x \mid h, A_t) = \frac{\mathbf{1}[x \in A_t(h)]\;P_\theta(x \mid h)^{1/\tau}}{\sum_{y \in A_t(h)} P_\theta(y \mid h)^{1/\tau}}
```

Equivalent logit form:

```math
Q_{\theta,\tau}(x \mid h, A_t) = softmax\left(\frac{\log P_\theta(x \mid h) + \log \mathbf{1}[x \in A_t(h)]}{\tau}\right)
```

with `log 0 = -∞` and normalization restricted to the live admissible set.

Boundary: this is a projection into an admissible candidate space, not a proof of semantic truth.

---

## 4. Deterministic Selection

To make selection deterministic, define a total tie-break order `≺` over tokens. The deterministic next-token operator is:

```math
x_t^* = \min_{\prec}\;\arg\max_{x \in A_t(h)} P_\theta(x \mid h)
```

This is the `τ → 0` limit of the masked distribution when tie-breaking is fixed and `A_t(h)` is non-empty:

```math
\lim_{\tau \to 0} Q_{\theta,\tau}(x \mid h, A_t) = \delta_{x_t^*}
```

If `A_t(h)=∅`, the transition fails closed:

```math
T(h) =
\begin{cases}
  h \circ x_t^*, & A_t(h) \neq \emptyset \\
  \bot, & A_t(h) = \emptyset
\end{cases}
```

`⊥` means exception, backtrack, quarantine, or rejection depending on the caller policy.

---

## 5. Sequence-Level Verification

A generated sequence `S = (x_0, …, x_n)` is accepted only if both prefix and global constraints hold:

```math
\forall t \in [0,n],\; \forall \phi \in \Phi_{prefix}: \phi(x_{0:t}) = 1
```

and:

```math
\forall \psi \in \Phi_{global}: \psi(S) = 1
```

The accepted artifact set is:

```math
K = \{S \in X^* \mid Valid_G(S)=1 \land \forall \phi \in \Phi_{prefix}:\phi(S)=1 \land \forall \psi \in \Phi_{global}:\psi(S)=1\}
```

For `CIP-01`, `Φ_global` includes at minimum:

- `claim_status` validity;
- falsification boundary presence;
- protocol/checklist mapping;
- provenance record presence;
- artifact destination or TTL state;
- external verification evidence when promoted to accepted artifact.

---

## 6. Acceptance Policy

`DIM-01` converts probabilistic generation into deterministic acceptance policy:

```text
stochastic distribution → masked candidate distribution → deterministic selection → global verifier → ACCEPT | QUARANTINE | REJECT | ENTROPY
```

The policy is deterministic if the following are fixed:

```yaml
determinism_requirements:
  - model_snapshot_or_backend_contract
  - decoding_parameters
  - grammar_or_schema
  - prefix_invariants
  - global_invariants
  - tie_break_order
  - verifier_version
  - artifact_write_policy
```

If any requirement is not fixed, the claim must downgrade from `deterministic` to `bounded/reproducible under stated conditions`.

---

## 7. Failure Modes

```yaml
failure_modes:
  empty_constraint_set:
    result: bottom
    action: backtrack_or_quarantine
  empty_live_admissible_set:
    result: bottom
    action: relax_non_blocker_constraints_or_quarantine
  schema_pass_global_fail:
    result: reject
    action: preserve_as_negative_result_if_informative
  verifier_missing:
    result: quarantine
    action: require_external_verification_before_promotion
  tie_break_unfixed:
    result: nondeterministic_selection_risk
    action: define_total_order_or_downgrade_claim
  backend_nondeterminism:
    result: reproducibility_boundary_required
    action: pin_backend_or_record_boundary
```

---

## 8. CIP-01 Integration

`DIM-01` implements the formal mechanism behind `CIP-01-INF-01`:

```yaml
cip_01_inf_01:
  metric: inference_compression_gate
  pass_condition: promoted artifact passes constrained decoding, schema validation, invariant checks, deterministic tie-break, and external verification
```

No `CIP-01` artifact may be promoted from candidate to accepted artifact unless it belongs to `K` or has an explicit `QUARANTINE` state with TTL.

---

## 9. Falsification Condition

`DIM-01` is falsified as a deterministic acceptance mechanism if:

1. two runs with identical determinism requirements produce different accepted artifacts;
2. a sequence outside `K` is accepted;
3. a candidate bypasses global verification;
4. an empty constraint set fails open instead of returning `⊥`;
5. an empty live admissible set fails open instead of returning `⊥`;
6. tie-breaking is ambiguous while the system still claims determinism.

---

## 10. Summary

`DIM-01` does not make language generation metaphysically certain. It makes artifact acceptance formally bounded:

```text
probabilistic generator + hard constraints + deterministic tie-break + verifier = deterministic acceptance policy
```

That is the useful engineering claim. Anything stronger is decorative overreach wearing a lab coat.
