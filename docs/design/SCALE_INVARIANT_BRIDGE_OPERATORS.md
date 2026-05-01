# Scale-Invariant Bridge Operator Candidates

claim_status: derived
status: design only — **no implementation, no measurement**
parent_doc: [`docs/roadmap/M_INVARIANT_M2_ROADMAP.md`](../roadmap/M_INVARIANT_M2_ROADMAP.md) — PR M2.4
prior:
- PR #171 — `INVALID_HWI` verdict
- PR M2.2 — `INVALID_OPERATOR` finding (JSD-as-Fisher proxy
  underestimates HWI bound on smooth Gaussian shift)

## Purpose

PR M2.2 demonstrated that `M = H / (W₂ · √JSD)` is not the
Otto-Villani HWI saturation it claims to be: even on textbook smooth
Gaussian translations, the JSD-based proxy violates the HWI bound at
unit scale because JSD ≪ true Fisher information. PR #171's
`INVALID_HWI` verdict is a special case of this structural failing.

This document is design-only. It enumerates candidate operator
classes whose sanity bound is **either**

(a) genuinely scale-invariant on the position axis, **or**
(b) does not depend on a position axis at all,

so that the resulting score has a well-defined cross-substrate
interpretation. **No code is written here. No measurement is
performed.**

## Non-negotiable rule

> An operator is admissible for the bridge only if its scale-
> invariance can be proven on analytic distributions before the
> operator is ever evaluated on substrate data.

If a candidate requires a substrate-specific bandwidth or a tuned
exponent to behave on synthetic controls, it is disqualified at the
design stage.

## Decision criteria

Each candidate is evaluated on five orthogonal axes:

- **Invariance property** — under what transformations of the input
  the score is provably constant.
- **Required assumptions** — what the candidate needs from the
  inputs (continuity, finite moments, bounded support, etc.).
- **Positive control** — analytic case where the candidate must
  return a known non-trivial value.
- **Negative control** — analytic case where the candidate must
  return ≈ 0 or a known low value.
- **Failure mode** — the most likely way the candidate can go
  wrong.

## Candidate 1 — Normalised Wasserstein ratio

### Formula

`ŝ(p, q) = W₂(p, q) / κ(p, q)`

where the **characteristic scale** `κ` is one of:

- `κ_support = max(supp p ∪ supp q) − min(supp p ∪ supp q)` — total support width;
- `κ_MAD = median(|x − median(p ∪ q)|)` — robust scale;
- `κ_std = √(0.5 · (Var(p) + Var(q)))` — average standard deviation.

### Invariance property
By construction, `ŝ` is invariant under affine rescaling
`x → s·x + b` because both numerator and denominator scale by `|s|`.

### Required assumptions
Finite second moments (for `κ_std`) or compactly supported
distributions (for `κ_support`).

### Positive control
Two Gaussians `N(0, 1)` vs `N(2, 1)`: `ŝ_std → |Δμ| / σ_avg = 2`.

### Negative control
Identical distributions: `W₂ = 0` so `ŝ → 0`.

### Failure mode
If the chosen `κ` collapses to zero (e.g. both distributions are
delta-functions at the same point), the ratio diverges. Must clamp
or fall back to an absolute bound.

### Why it might bridge MFN ↔ BN-Syn
Removes the position-axis units that broke PR #171. The resulting
score has the same numerical range whether `p`, `q` live on a pixel
grid or on a voltage axis.

### Why it might not
Reduces information content to a single transport cost ratio. Two
substrates can match on `ŝ` while differing dramatically in finer
moments of the distribution.

---

## Candidate 2 — Entropy-regularised OT divergence (Sinkhorn)

### Formula

`Sε(p, q) = OTε(p, q) − 0.5 · (OTε(p, p) + OTε(q, q))`

where `OTε` is the entropy-regularised optimal transport cost with
regulariser `ε`. The Sinkhorn divergence is symmetric, positive, and
zero iff `p = q`.

### Invariance property
Under `x → s · x` with `ε` rescaled to `ε · s²`, the divergence is
invariant. The auto-bandwidth rule `ε = c · W₂(p, q)²` (where `c` is
a fixed dimensionless constant chosen on synthetic controls) gives
adaptive scale invariance.

### Required assumptions
Compact support OR finite second moments. Numerically stable
implementations exist for both 1-D and 2-D inputs.

### Positive control
`Sε(N(0,1), N(2,1))` should be a known monotone function of `Δμ`.

### Negative control
`Sε(p, p) = 0` exactly (this is the de-biased construction's
purpose).

### Failure mode
Choice of `c` in the auto-bandwidth rule is itself a parameter. Must
be locked from synthetic controls before substrate data is observed.

### Why it might bridge MFN ↔ BN-Syn
Smoother geometry than raw `W₂`. The de-biased construction
suppresses the support-mismatch artefact that exploded HWI in PR
#171.

### Why it might not
Implementation cost is higher than `W₂` alone (Sinkhorn iterations).
The auto-bandwidth choice is one extra pre-registration commitment.

---

## Candidate 3 — Jensen-Shannon trajectory divergence

### Formula

`JS_traj(P, Q) = ⟨JSD(P_t, Q_t)⟩_t`

where `P_t`, `Q_t` are the time-resolved distributions of the two
substrates and `JSD` is the standard Jensen-Shannon divergence.

### Invariance property
JSD ∈ `[0, ln 2]` is bounded and **independent of position-axis
units** because it is a pure information-theoretic quantity on
normalised densities. No `W₂` enters; therefore no coordinate-scale
artefact.

### Required assumptions
Time-resolved snapshots are well-defined for both substrates.
Bandwidth (KDE) must be locked before measurement.

### Positive control
`JS_traj` between deterministic limit-cycle vs random-noise
trajectories must approach `ln 2` (maximum JSD).

### Negative control
`JS_traj(P, P) = 0`.

### Failure mode
Drops all geometric information about W₂. Any cross-substrate
agreement on `JS_traj` says only that the *distributions* match, not
that the *transport between them over time* matches.

### Why it might bridge MFN ↔ BN-Syn
The most explicitly scale-free candidate. If the two substrates
share a shape evolution pattern (independent of value units), this
captures it.

### Why it might not
A bridge based purely on JSD has no notion of *transport speed*.
Two systems that visit the same densities in different orders will
look identical.

---

## Candidate 4 — Fisher-Rao / Hellinger geometry

### Formula

`d_H(p, q) = √(0.5 · ∫ (√p − √q)² dx)` — Hellinger distance,
or equivalently the geodesic on the Fisher-Rao manifold:

`d_FR(p, q) = arccos(∫ √(p · q) dx)`.

### Invariance property
Hellinger and Fisher-Rao distances are invariant under coordinate
reparametrisation of the position axis (a fundamental property of
the Fisher information manifold). They depend only on the densities.

### Required assumptions
Both distributions strictly positive on a shared support (or
sufficiently smooth KDE).

### Positive control
`d_H(N(0,1), N(2,1))` has a known closed form:
`d_H² = 1 − exp(−Δμ²/8)`. Useful as a test target.

### Negative control
`d_H(p, p) = 0`.

### Failure mode
Discards transport information entirely (same caveat as JSD).
Behaves nicely on smooth densities; less robust on near-degenerate
KDE.

### Why it might bridge MFN ↔ BN-Syn
Most rigorous information-geometric candidate. No external
coordinate enters.

### Why it might not
Same as Candidate 3: no transport notion. Cannot distinguish two
systems that share densities but differ in dynamic ordering.

---

## Candidate 5 — Spectral operator

### Formula

Compare the substrates through their power spectral density (PSD)
or autocorrelation function:

`δ_PSD(P, Q) = ‖log Ŝ_P(f) − log Ŝ_Q(f)‖_{L²(df)}`

where `Ŝ_X(f)` is the PSD of substrate `X`'s primary observable.

### Invariance property
Frequency-axis invariance under sampling-rate matching (frequencies
in `Hz`, not bin indices). The score depends on spectral *shape*,
not on absolute amplitude.

### Required assumptions
Stationary or piecewise-stationary trajectories long enough for
PSD estimation. Common in signal-processing literature.

### Positive control
Two AR(1) processes with the same pole have identical PSD shapes;
`δ_PSD → 0`.

### Negative control
White noise vs limit-cycle: `δ_PSD` large.

### Failure mode
Stationarity assumption fails on transient substrates (e.g.
morphogenesis is intrinsically non-stationary).

### Why it might bridge MFN ↔ BN-Syn
Frequency-domain comparison sidesteps both the position-axis and
the value-axis units. Strong precedent in dynamical-systems
literature.

### Why it might not
Spectra are unbounded; need a robust normalisation. Loses phase
information.

---

## Decision table

| candidate | invariance | impl cost | preserves transport? | preserves dynamics? |
|---|---|---|---|---|
| 1. Normalised W₂ ratio | affine, by construction | low | yes | partially |
| 2. Entropy-regularised OT | affine with auto-bandwidth | medium | yes | partially |
| 3. JS trajectory divergence | scale-free | low | no | yes (time-resolved) |
| 4. Fisher-Rao / Hellinger | reparam-invariant | medium | no | no |
| 5. Spectral operator | frequency-axis | medium | indirect | yes (in stationary regime) |

## Recommendation

The roadmap rule is: **pick at most two for prototype, one
geometry-preserving and one manifold-free.**

- **Geometry-preserving choice: Entropy-regularised OT (Candidate 2).**
  Handles support mismatch better than raw `W₂`, has clear
  scale-invariance after `ε`-rescaling, has a debiased construction
  that avoids the clamp saturation seen in PR #171.
- **Manifold-free choice: JS trajectory divergence (Candidate 3).**
  No position-axis at all. The cleanest separation from the failure
  mode of PR #171. Pairs well with Candidate 2: if the geometric
  one shows agreement and the manifold-free one shows disagreement,
  the bridge is shape-only and not transport-aware.

Candidates 1, 4, 5 remain *documented alternatives* and may enter
later contracts if neither prototype passes its controls.

## What would falsify each prototype

For Entropy-regularised OT:
- positive control fails to give a monotone function of `Δμ` on
  Gaussians;
- de-biased divergence is not zero on `Sε(p, p)` within numerical
  tolerance;
- auto-bandwidth `ε = c · W₂²` requires `c` to depend on substrate
  to match analytic targets.

For JS trajectory divergence:
- `JS_traj(P, P) ≠ 0` after KDE smoothing on the same trajectory
  (would indicate pathological smoothing);
- on the deterministic-limit-cycle vs noise control, the divergence
  does not approach `ln 2`.

If any of these conditions is met for both prototypes, the operator
path is rejected and the M2.5 pre-registration must declare the
bridge family closed under both Path A (spatial embedding) and Path
B (scale-invariant operator) options.

## What this document is and is not

- It IS the design space for the operator-replacement path of M2
  bridge recovery.
- It IS the input to PR M2.5's pre-registration of Path B
  (`SCALE_INVARIANT_OPERATOR_BRIDGE`).
- It is NOT an implementation. No code lives here.
- It is NOT a claim about the substrate. The current status remains
  `OPEN_NARROWED` per `contracts/M_BRIDGE_CLAIM_STATUS.yaml`.
- It does NOT promote `current_status`, mutate the registry, or
  amend any PR #171 contract.
