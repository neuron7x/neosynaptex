# Canonical Position

> γ ≈ 1.0 is a **candidate cross-substrate regime marker** of metastable critical regimes in coupled, productive dynamical systems. The protocol treats it as a **falsifiable hypothesis under active test** — not a confirmed correlate, not a universal law, not a definition of intelligence. Current evidence is **substrate-dependent**: `evidence/replications/registry.yaml` records both supportive and falsifying verdicts.
>
> The Neosynaptex protocol requires **independent replication**, **falsification tests**, **adversarial controls**, and **active counter-example search**. Levin provides the biological precedent for distributed agency; the operational bridge between **H** (integration horizon), **C** (coordination), **γ** (metastability), and **P** (productivity) is under audit **directly at every level of systemic description**.
>
> **Excluded:** pareidolia, mystification, teleology, romanticisation.
>
> The canon holds **only** while it survives hard contact with reality.

---

## Status of this statement

**Canonical.** This file is the single reference every manuscript, README, release note, and agent-generated artefact must align with when describing the scope of the γ claim.

**Forbidden rewordings.**

- "γ ≈ 1 defines intelligence / cognition / agency."
- "γ ≈ 1 proves [anything about a specific substrate without the four falsification requirements being met on that substrate]."
- Any visual or pareidolic image treated as evidence.
- Any statement that conflates biological precedent (Levin) with a proven law about software or LLM systems.

## Required engagements before any promotion above "candidate marker"

1. **Independent replication** — at least one party who did not build the estimator reproduces the γ value from raw substrate output.
2. **Falsification tests** — pre-registered predictions with explicit kill criteria (see `docs/protocols/levin_bridge_protocol.md` Step 5).
3. **Adversarial controls** — shuffle, matched-noise, overcoupled-collapse, undercoupled-fragmentation (see `evidence/levin_bridge/controls.yaml`).
4. **Counter-example search** — active attempt to find substrates or regimes where the correlate breaks.

## Measured limit of the estimator (2026-10-11)

γ̂ ≈ 1 is reproduced by linear, non-critical processes. Under the estimators in this
tree, linear 1/f noise gives γ̂ = 1.016 ± 0.058, AR(1) with φ = 0.9 gives
0.863 ± 0.107, and `cost := 1/topo` gives exactly 1.0 with verdict METASTABLE
(`results/gamma_specificity/run_v1.json`, verdict NOT_SPECIFIC). An observed
γ̂ ≈ 1 is therefore **not, by itself, evidence of a critical or metastable
regime**. This limits what a measurement can show; it does not decide whether
critical systems produce γ ≈ 1. The programme that follows from it is
`docs/RESEARCH_DIRECTION.md`.

## Governance

Any change to the wording above is a structural claim-level change. It MUST be made in a commit whose diff is reviewed specifically against these constraints, not swept into a larger PR.

## Related canon

- `docs/protocols/levin_bridge_protocol.md` — falsification-first bridge protocol.
- `evidence/levin_bridge/horizon_knobs.md` — per-substrate operational knobs.
- `evidence/levin_bridge/hypotheses.yaml` — machine-readable preregistration.
- `evidence/levin_bridge/controls.yaml` — adversarial control families.
- `evidence/PREREG.md` — commit-SHA-pinned adapter/measurement pre-registration.
- `experiments/lm_substrate/README.md` — existing falsification record for stateless LLM-API inference (γ ≈ 0).
