# Geometric Mechanics of Systemic Causality

## Status
- Type: bounded conceptual artifact
- Version: v1.0
- Scope: methodological specification for recursive systems integration

## Canonical thesis
Systemic integration operates on hidden-state dynamics, not isolated events.

\[ y(t) = h(x(t)) + \eta(t), \quad \dot{x} = F_\theta(x,u,t) \]

The practical intervention target is the generator of trajectories (field, constraints, boundaries), not the surface projection.

## Recursive loop closure
\[
\text{Perception} \rightarrow \text{Inference} \rightarrow \text{Action} \rightarrow \text{Feedback} \rightarrow \text{Compression} \rightarrow \text{Architecture Update} \rightarrow \text{Next Action}
\]

Operationally, this aligns with EAI verified closure:

\[
\text{Intent} \rightarrow \text{Inference} \rightarrow \text{Falsification} \rightarrow \text{Boundary} \rightarrow \text{Artifact} \rightarrow \text{Retention} \rightarrow \text{Updated Intent}
\]

## Core formal blocks
1. **State/observation separation**
   - Events are projections: \(e_i = h(x(t_i))\).
2. **Trajectory generation**
   - Dynamics defined by \(F_\theta\), constraints, and boundary flows.
3. **Leverage search**
   - \(\theta^* = \arg\max_i |\partial Y/\partial \theta_i|\).
4. **Feedback stability**
   - Closed-loop behavior determined by the spectrum of the closed operator.
5. **Delay sensitivity**
   - Delayed feedback can shift stable systems into oscillatory/unstable regimes.
6. **Boundary correctness**
   - Mis-specified \(\partial\Omega\) induces false causal attribution.

## Engineering invariants
- No event interpretation without hidden-state hypothesis.
- No intervention without declared boundary and failure criterion.
- No claimed learning without artifact retention and architecture update.
- No promotion without falsification and reproducibility.

## Anti-patterns
- Event-only reaction loops.
- Symptom suppression without field change.
- Local optimization with global entropy increase.
- Feedback without compression into reusable constraints.

## Integration contract for this repository
This artifact maps directly to EAI modules:
- `core/eai/engine.py`: trajectory-level decision orchestration.
- `core/eai/integrator.py`: recursive architecture update.
- `core/eai/leverage.py`: leverage-point sensitivity ranking.
- `core/eai/psychophysiology.py`: latent-state to observable projection.

## Final canonical statement
Do not repair only the manifestation. Update the law of motion that generates it.
