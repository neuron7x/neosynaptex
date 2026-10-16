# DNCA -> DOPA-CLOSURE v2: routing-only integration (experimental)

## Scope and scientific boundary

This vertical slice connects the **real executed DNCA** shared predictive state
(`agents/src/neuron7x_agents/dnca/`) to the existing
`DopaClosureV2Allocator.priority_of_verification`, with budget reservations
via `BudgetLedger` and the existing `ConstructContext` gate.

**It does not establish any gain in cognitive accuracy or verification closure.**
The DOPA-CLOSURE theory remains **UNTESTED** per
`evidence/dopa_closure/RETRACTION.md`. A previous proxy-based test was retracted.
The value estimator behind DNCA RPE is not independently qualified for truth
verification routing. Positive gain is *experimental*, not a validated improvement.

## Definitions (prior to use)

- **DNCA**: Distributed Neuromodulatory Cognitive Architecture; only actual
  `neuron7x_agents.dnca.orchestrator.DNCA` instances are accepted by the live API.
- **SPS**: DNCA shared predictive state; `snapshot()` produces a detached record.
- **Prediction-error magnitude**: the L2 norm of SPS prediction error, normalized
  as `e/(1+e)`, `e >= 0`; this is *not* verified claim truth.
- **Signed valence**: bounded `[-1,1]` dopamine TD-like signal before asymmetric gain;
  never absolute-valued for the sign-control experiment.
- **Inhibition**: SPS inhibition signal in `[0,1]`; values above a configurable
  threshold force a quarantine/hold reservation.
- **Claim evidence**: independent per-claim metadata supplied by the caller,
  never derived from the neural dopamine or serotonin scalars.
- **Dopamine gain**: bounded `[0,0.25]`; zero is the ablation; positive values
  perturb *priority only* in an experimental arm.
- **Closure**: an independently verified evidence-bound claim outcome.
  This bridge cannot emit closure; `verification_result` is always `not_run`.

## Runtime flow

1. Run a real `DNCA.step()` on a task observation, then capture SPS.
2. `route_live_dnca()` checks DNCA type and requires an executed positive step.
3. Strictly validate SPS tensor shapes, finiteness, sign and unit bounds.
4. Attach independently provided `EvidenceInput` claim metadata.
5. Evaluate the existing `ConstructContext`; false => no routes or spending.
6. Calculate DOPA v2 baseline priority plus signed DA gain (experimental arm).
7. Apply inhibition hold, risk/reject thresholds and existing budget action costs.
8. Return **queued actions** and budget reservations only, never truth labels.

```python
# Run from repository root; install agents package first:
# python -m pip install -e agents
import torch
from neuron7x_agents.dnca.orchestrator import DNCA
from core.eai.dnca_modulated_router import EvidenceInput, route_live_dnca
from core.eai.dopa_construct_gate import ConstructContext

model = DNCA(state_dim=16, hidden_dim=32, seed=42)
model.step(torch.zeros(16), reward=0.1)
claim = EvidenceInput("claim-1", 0.6, 0.4, 0.2, 0.8, 0.55)
# Flags below are merely a synthetic integration fixture, NOT empirical evidence.
fixture = ConstructContext(True, True, False, False, True, True)
result = route_live_dnca(model, [claim], fixture, dopamine_gain=0.0)
# result is Ok(...status='ROUTING_ONLY'...) or Err(...).
```

## Fail-closed invariants

- F1: missing or unexecuted DNCA => `Err`, never fabricated fallback signal.
- F2: missing, multi-element, out-of-domain or non-finite SPS fields => `Err`.
- F3: failed construct gate => `INSTRUMENT_INADMISSIBLE`, no routes/spend.
- F4: dopamine gain changes prioritization only; no gain changes epistemic gates.
- F5: inhibition overrides positive DA; route becomes quarantine/hold.
- F6: budget reservations conserve the envelope, never allow negative remaining.
- F7: `CLOSED` and `VERIFIED` are unreachable in the bridge result.
- F8: a detached SPS projection is marked `UNTRUSTED_SPS_PROJECTION`, not
  mislabeled as an actual executed DNCA runtime.
- F9: no numerical positive or negative result is allowed as theory verdict
  without a qualified signal, independent verifier, and budget-matched baseline.

## Local verification (GitHub Actions are unavailable)

```bash
python -m pip install -e '.[dev]' -e agents
python -m pytest -q tests/dopa_closure_v2/test_dnca_modulated_router.py
python -m ruff check core/eai/dnca_modulated_router.py tests/dopa_closure_v2/test_dnca_modulated_router.py
python -m mypy core/eai/dnca_modulated_router.py
```

These commands must be executed and logged on a capable local machine. GitHub
merge status is not an empirical test result. There is no end-to-end benchmark
claim until the vRPE signal and external verifier meet preregistered validity
criteria.

## Next experiments

Pre-register a 2x2 factorial exploration/pursuit design with an identical
verification budget and matched compute across arms. Compare DA gain=0 to
positive gain using signed-value negation as an actual negative control.
Use an external independently qualified verifier and an endpoint measuring
*verified closure*, not classification accuracy. Prefer the strongest
uncertainty-only baseline. Fail closed on missing provenance, weak verifier,
uncalibrated signal or missing CI/local replay evidence.
