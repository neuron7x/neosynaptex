# HWI scale-dependence diagnostics

claim_status: derived
scope: synthetic distributions only — no substrate, no bridge claim
parent: [`docs/roadmap/M_INVARIANT_M2_ROADMAP.md`](../../docs/roadmap/M_INVARIANT_M2_ROADMAP.md) PR M2.2

## Purpose

PR #171 reported `INVALID_HWI` and the narrative explained that the
`H ≤ W₂·√I` inequality is scale-dependent on the position axis. This
harness **quantifies** that statement on five synthetic distribution
pairs whose ground truth is known. No substrate is involved.

## How to run

```
python experiments/m_invariant_scale_diagnostics/run.py
```

Output: `results/m_invariant_scale_diagnostics/run_v1.json`. Stdout
prints the per-case M trajectory across coordinate scales
`s ∈ {0.01, 0.1, 1.0, 10, 100}` and a final verdict.

## Verdicts

| verdict | meaning |
|---|---|
| `SCALE_DEPENDENT` | at least one case shows M change > 0.05 under axis rescale, OR clamp saturation observed |
| `SCALE_STABLE` | no case shows M change > 0.05 (would refute PR #171's interpretation) |
| `INVALID_OPERATOR` | smooth control case violates HWI at unit scale — operator unusable on textbook input |

## Empirical finding (current run)

The harness reports `INVALID_OPERATOR`. This is **stronger** than
`SCALE_DEPENDENT` and is itself the central finding of M2.2.

For a textbook Gaussian shift `p = N(0,1)`, `q = N(2,1)` at unit scale:

- `H = KL(p||q) ≈ 2.0`
- `W₂(p,q) = |μ_p - μ_q| = 2.0`
- True relative Fisher `I_F(p||q) = (μ_p − μ_q)² / σ² = 4.0` →
  `W₂ · √I_F = 4.0 ≥ H` → Otto–Villani HWI holds.
- MFN's JSD substitution gives `I = JSD(p,q) ≈ 0.33` →
  `W₂ · √I_JSD ≈ 1.15 < H` → HWI bound **violated**.

Conclusion: the operator `M = H / (W₂ · √JSD)` is **not** the HWI
saturation ratio it claims to be. The published `M ≈ 0.106` on
MFN Gray-Scott was below 1 only because pixel-coordinate W₂ was large
enough to keep the unbalanced ratio in `[0,1]`. PR #171's
`INVALID_HWI` is a **special case** of this structural failing, not a
substrate-specific quirk.

## Cases (synthetic)

1. **Gaussian shift** — `p = N(0,1)`, `q = N(2,1)` (translation only).
2. **Gaussian variance** — `p = N(0,1)`, `q = N(0,4)` (variance only).
3. **Bimodal shift** — symmetric mixtures; q is shifted by 0.5.
4. **PDE-like wide** — uniform on `[0,32]` vs `[4,28]` (range similar to MFN pixel-coord).
5. **BN-like narrow** — narrow Gaussians on `[-0.08, 0.01]` (similar to MFN Gray-Scott activator value range).

## Forbidden interpretations

This harness is **synthetic only**. Per
`contracts/M_BRIDGE_CLAIM_STATUS.yaml`, none of these claims may be
derived from the output:

- forbidden: M is universal
- forbidden: Turing Gap closed
- forbidden: MFN BN-Syn bridge confirmed

The lint tool in `tools/audit/m_bridge_claim_lint.py` enforces the
ban on positive assertion of the registry's forbidden_claims across
the docs tree.

## Determinism

`np.random.default_rng(20260501)` seeds all sample generation. KDE
(Scott's bandwidth) is deterministic given samples. Output JSON is
byte-identical across re-runs.
