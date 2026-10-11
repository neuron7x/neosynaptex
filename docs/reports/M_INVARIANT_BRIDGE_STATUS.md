# M-Invariant Bridge Status

claim_status: derived
last_updated: 2026-05-01
authority: [PR #171](https://github.com/neuron7xLab/neosynaptex/pull/171) merge commit `27fc29a`
machine_registry: [`contracts/M_BRIDGE_CLAIM_STATUS.yaml`](../../contracts/M_BRIDGE_CLAIM_STATUS.yaml)

## Current Verdict

**`INVALID_HWI`**.

The contracted MFN ↔ BN-Syn bridge experiment (PR #171, contract
`M_INVARIANT_BNSYN_MFN_BRIDGE_v1.2`) returned `INVALID_HWI`. The HWI sanity
inequality

```
H ≤ W₂ · √I
```

was violated on 94–100 % of contracted substrate samples under the 1-D
value-axis KDE-density operator. The clamp `M = min(M, 1)` saturated both
substrates to 1.0; raw numbers in `results/m_invariant_bridge/run_v1.json`.

## What Failed

The **1-D value-axis specialisation** of the M operator on the
two-substrate pair (MFN Gray-Scott, BN-Syn AdEx). HWI is scale-dependent on
the position axis: pixel-grid coordinates (range ≈ 32 units) give the
published M ≈ 0.106; value-axis units (mV for BN-Syn, ≈ 0.08 for MFN
activator) collapse `W₂ · √I` below `KL`, so the bound fails by
construction.

## What Did Not Fail

The broader possibility of a cross-substrate bridge **did not fail**. Only
this operator, on this axis, under this contract, failed. The 1-D
specialisation is one of many possible operationalisations.

## Forbidden Reinterpretations

These reinterpretations are **explicitly rejected**. Tests
(`tests/test_m_bridge_claim_status.py`) and a documentation linter
(`tools/audit/m_bridge_claim_lint.py`) reject docs that assert any of
these outside an explicit "Forbidden" / "Rejected" / "Disavowed"
context.

- `M=1.0 saturation is not convergence.` Both substrates hit the clamp
  ceiling because HWI failed; equality is a numerical artefact, not a
  match.
- `White-noise null separation is not bridge validation.` The operator
  rejecting noise (M ≈ 0.075 vs 1.0) does not imply that it has identified
  a shared regime — it only implies the operator is non-degenerate on
  random input.
- `INVALID_HWI is not FAIL_OFFBAND.` The first means the operator is
  unsuitable for the data; the second means the substrates do not converge
  under a valid operator. The PR #171 result is the former.
- `This result cannot support Turing Gap closure.` Turing Gap remains
  `OPEN_NARROWED` until a different operator or a different embedding
  passes a pre-registered contract.

## Narrowed Hypothesis

The published `M ≈ 0.106` is currently a **PDE-coordinate invariant**: a
property of the 2-D HWI operator applied to fields on a discretised
spatial grid. A portable cross-substrate bridge requires either:

1. **Honest spatial embedding of BN-Syn** so that the original 2-D
   operator can be applied without inventing geometry post-hoc.
   Design candidates in
   [`docs/design/BNSYN_SPATIAL_EMBEDDING_FOR_HWI.md`](../design/BNSYN_SPATIAL_EMBEDDING_FOR_HWI.md)
   (separate PR M2.3).
2. **A scale-invariant replacement operator** whose sanity bound does
   not depend on coordinate units. Candidates in
   [`docs/design/SCALE_INVARIANT_BRIDGE_OPERATORS.md`](../design/SCALE_INVARIANT_BRIDGE_OPERATORS.md)
   (separate PR M2.4).

## Distinction Between Failed Operator, Failed Axis, and Open Program

| layer | status | evidence |
|---|---|---|
| operator: 1-D value-axis HWI on KDE densities | **failed** for MFN ↔ BN-Syn pair | PR #171 verdict `INVALID_HWI` |
| axis: substrate-natural value range as coordinate | **failed** as scale for HWI | scale-dependence shown in PR #171 narrative; quantified in PR M2.2 |
| program: cross-substrate metastable regime hypothesis | **open, narrowed** | no operator has passed a pre-registered contract; #171 closes one operator only |

## Next Phase

**M2 Bridge Recovery.** Five-PR split tracked in
[`docs/roadmap/M_INVARIANT_M2_ROADMAP.md`](../roadmap/M_INVARIANT_M2_ROADMAP.md).
Immediate next PR is M2.2 (synthetic scale-dependence diagnostics, no
substrate measurement).

## Disavowed Claims (machine-checked)

The strings below are forbidden in repository documentation outside
explicit disavowal blocks. The lint tool walks `docs/` and rejects any
appearance.

- `M is universal`
- `Turing Gap closed`
- `MFN and BN-Syn share M invariant`
- `M=1.0 proves convergence`
- `INVALID_HWI supports the bridge`
- `MFN BN-Syn bridge confirmed`

## Reproduction

```
python experiments/m_invariant_bridge/run.py
```

Result is deterministic; `verdict` field stays `INVALID_HWI` under the
locked contract `contracts/M_INVARIANT_BNSYN_BRIDGE.yaml` v1.2.
