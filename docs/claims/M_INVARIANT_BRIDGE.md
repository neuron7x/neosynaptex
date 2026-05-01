# M-invariant cross-substrate bridge: MFN ↔ BN-Syn

claim_status: derived

## Question

Does the unified score `M = H/(W₂√I)` — measured at ≈ 0.106 during MFN
Gray-Scott Turing morphogenesis (Otto-Villani HWI saturation) — recover a
comparable value when the same operator is applied to a BN-Syn AdEx spiking
trajectory? If yes AND nulls fail to land in the same band, this is
cross-substrate evidence of a shared metastable regime. If no, the hypothesis
narrows to PDE-class systems.

## Pre-registration

Contract: [`contracts/M_INVARIANT_BNSYN_BRIDGE.yaml`](../../contracts/M_INVARIANT_BNSYN_BRIDGE.yaml)
(v1.2, sha256 in results/m_invariant_bridge/run_v1.json).
Threshold (relative deviation): 0.20 — mirrors the cross-PDE invariance
threshold used in `substrates/mfn/scripts/m_invariant_three_substrates.py`
(CV<20%). Two pre-registered nulls:

- white-noise on the voltage axis (must lie outside the band),
- time-shuffled BN-Syn trajectory (must lie outside the band).

Verdict logic and forbidden post-hoc actions are listed in the contract.

## Result

Verdict: **INVALID_HWI** — the operator's HWI sanity inequality
`H ≤ W₂·√I` is violated on the contracted data above the 5%-of-samples
tolerance. Numbers:

| configuration         | M_morph (mean ± std) | HWI viol. fraction |
|-----------------------|----------------------|--------------------|
| MFN Gray-Scott (1D)   | 1.000 ± 0.000        | 94–100%            |
| BN-Syn AdEx (1D)      | 1.000 ± 0.000        | 94–100%            |
| Null: white noise     | 0.075 ± 0.011        | 0%                 |
| Null: time-shuffled   | 0.810 ± 0.308        | 44–100%            |

`compute_seconds`: ~4.0; n=5 seeds × 2000 BN-Syn steps × 60 MFN steps;
contract sha256 binds the YAML hash to the run.

## Interpretation

The HWI saturation ratio is **scale-dependent on the position axis**. The
canonical MFN value `M ≈ 0.106` is computed with positions on the 2-D
pixel-coordinate grid (range ~32 units), where W₂ has plenty of magnitude
relative to KL. When the operator is reduced to its 1-D specialisation on
the **field's value axis** (KDE-smoothed density over voltage in mV for
BN-Syn, or over concentration for MFN Gray-Scott), the position units shrink
to the substrate's value range:

- BN-Syn: voltage in mV, range ≈ 120, std ≈ 5.
- MFN Gray-Scott (this run): activator value in [-0.077, +0.006], range ≈ 0.08, std ≈ 0.02.

In both cases W₂·√I is small relative to KL, so HWI is violated by
construction and the published "M as HWI saturation in [0,1]" interpretation
loses its grounding. The clamp `M = min(M, 1)` then saturates both substrates
to 1.0 — they appear "equal" only because both have hit the ceiling.

The white-noise null nevertheless separates cleanly from the substrate runs
(M ≈ 0.075 vs 1.0). This is informative: the operator IS selective against
random noise on the value axis. It is NOT, however, in a regime where it
gives a stable cross-substrate invariant.

## Honest narrowing

`M = H/(W₂√I)` as published is a **2-D-pixel-coordinate** invariant for PDE
fields, not a substrate-portable invariant for arbitrary 1-D dynamical
systems. Building a true cross-substrate bridge requires either:

1. Inventing a position scale on BN-Syn that has the same Riemannian-manifold
   role as pixel-coordinates do for PDE fields (e.g., embedding neurons in a
   spatial topology such as cortical sheet coordinates) — and then computing
   the 2-D operator there. This is a substantive modelling decision, not a
   tuning knob.
2. Replacing the operator with one whose sanity bound is scale-invariant
   (e.g., entropy-regularised OT divergence with auto-bandwidth, or a
   manifold-free information-geometric M-proxy).

Both paths are out of scope for this PR. The contract authorised
"investigate before retry" on `INVALID_HWI`; per the same contract,
`THRESHOLD_REL` was not relaxed and seeds were not dropped.

## Reproduction

```
python experiments/m_invariant_bridge/run.py
```

Determinism: BN-Syn seeded via `bnsyn.rng.seed_all`; MFN via
`SimulationSpec.seed`; KDE deterministic given samples; verdict deterministic
given pre-registered constants.

## What this PR does and does not claim

- It DOES: pre-register a kill-criterion, run the contracted experiment,
  publish the raw numbers, and accept the verdict the contract dictated.
- It DOES NOT: assert that morphogenesis and spiking dynamics share a
  metastable regime. It also does NOT assert that no such bridge exists —
  only that the published 1-D specialisation of `M` is not the bridge.
- It DOES NOT: widen any pre-registered threshold or drop any seed.
