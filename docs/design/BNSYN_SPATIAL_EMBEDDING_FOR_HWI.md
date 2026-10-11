# BN-Syn Spatial Embedding for HWI

claim_status: derived
status: design only — **no implementation, no measurement**
parent_doc: [`docs/roadmap/M_INVARIANT_M2_ROADMAP.md`](../roadmap/M_INVARIANT_M2_ROADMAP.md) — PR M2.3
prior: [`docs/reports/M_INVARIANT_BRIDGE_STATUS.md`](../reports/M_INVARIANT_BRIDGE_STATUS.md), PR #171

## Purpose

The original 2-D HWI operator (`compute_hwi_components` in
`substrates/mfn/src/.../unified_score.py`) is defined on a square
spatial grid: every cell of a Gray-Scott concentration field
contributes a particle at pixel coordinates `(i, j)` with mass equal to
the local concentration. PR #171 attempted to apply the operator to
a BN-Syn voltage vector, which has no native 2-D embedding; the 1-D
specialisation that resulted violated the HWI sanity bound (see
`results/m_invariant_bridge/run_v1.json` and the structural finding
in PR M2.2 — `results/m_invariant_scale_diagnostics/run_v1.json`).

This document is design-only. It enumerates candidate ways to give
BN-Syn neurons a 2-D coordinate so that the **original** PDE-coordinate
operator can be applied honestly, and lists what each candidate
preserves and what it destroys. **No code is written here. No
measurement is performed.**

## Non-negotiable rule

> **Coordinates must represent a real modelling assumption, not a
> tuning knob.**

A coordinate scheme that is chosen because it makes the M number land
near 0.106 is the same as widening a pre-registered threshold: it
converts a measurement into a parameter search. Any candidate below
that requires post-hoc selection of `(N_x, N_y)`, kernel width, or
neuron-to-pixel assignment to give a particular M value is
disqualified at the design stage, before any data is observed.

## Decision criteria

For each candidate the table below evaluates four orthogonal axes:

- **Scientific legitimacy** — is the coordinate chosen for an
  independent physical reason, or invented to make M behave?
- **Implementation cost** — number of lines / dependencies / new
  contracts required.
- **Risk of post-hoc geometry** — how easy is it to retrofit the
  coordinate after seeing M?
- **Compatibility with current BN-Syn** — does the AdEx network
  already supply the inputs the embedding needs?

## Candidate 1 — Ring topology

### Definition
Place neuron `k` at angle `θ_k = 2πk/N` on a unit circle. The 2-D
embedding is `(cos θ_k, sin θ_k)`.

### Physical meaning
Common in coupled-oscillator literature when phase locality matters
(e.g. Kuramoto on a ring). Carries the assumption that adjacent
neuron indices have stronger coupling than distant ones — a property
that BN-Syn does **not** guarantee.

### What it preserves
- 1-D distance metric becomes a true Riemannian metric on `S¹`.
- W₂ on the ring is well-defined and bounded by `π`.
- Operator behaviour matches the published 2-D MFN setup if the ring
  embedding plus a 2-D toroidal grid is used.

### What it destroys
- Any non-local connectivity in BN-Syn becomes invisible to the
  geometry; the operator measures only locally-projected dynamics.
- Two neurons with identical voltage trajectories at opposite
  positions on the ring contribute to W₂ as if they were unrelated.

### Null model
Random angular permutation of neurons. If M after permutation is
indistinguishable from M on the original assignment, the ring
geometry adds no information.

### Failure mode
Connectivity in `substrates/bn_syn/src/bnsyn/sim/network.py` is
random / population-coded, not 1-D ring-coupled. Imposing ring
locality is an unjustified geometric assumption.

### Required tests
- Permutation null on neuron-to-angle assignment.
- Comparison against MFN's pixel-grid M on a Gray-Scott run mapped
  to the same ring (positive control).

---

## Candidate 2 — 2-D cortical sheet

### Definition
Place neurons on an `N_x × N_y` lattice (with `N_x · N_y = N`). Each
neuron has coordinates `(i Δ, j Δ)` for some lattice spacing `Δ`. The
embedding mimics how cortical neurons are arranged in vivo, with a
distance-dependent coupling kernel.

### Physical meaning
Strong analogue of cortical microcircuit literature. If the BN-Syn
network can be reconfigured so that synaptic weights respect a
distance kernel, this becomes a real modelling assumption rather
than a post-hoc fit.

### What it preserves
- 2-D pixel-coordinate operator applies directly: same code path as
  MFN Gray-Scott.
- Allows direct comparison with MFN at matched grid sizes (e.g.
  `8 × 8 = 64` for `N = 64`).

### What it destroys
- Forces `N` to be a perfect square or pads with dummies.
- Existing BN-Syn connectivity is currently random — must be
  retrofitted with a distance kernel before this embedding has any
  scientific meaning.

### Null model
Two nulls are required:

1. random `(i, j)` assignment of neurons to lattice cells with the
   distance kernel applied — should drop M relative to a coupling-
   matched assignment;
2. preserved `(i, j)` assignment but random connectivity — should
   destroy any M that depends on dynamics rather than geometry.

### Failure mode
If both nulls give the same M as the contracted assignment, the
embedding is decorative and the operator is measuring geometry, not
dynamics.

### Required tests
- Re-implement BN-Syn coupling with the distance kernel; verify that
  removing the kernel collapses M to either null.
- Positive control: a 2-D PDE with known M on the same lattice.

---

## Candidate 3 — Graph spectral embedding

### Definition
Build the connectivity graph Laplacian `L` from BN-Syn's synaptic
weight matrix; place each neuron at the coordinate given by its
2-D Laplacian eigenvector entries (the second and third eigenvectors,
skipping the trivial constant). This is classical spectral embedding.

### Physical meaning
Geometry is *derived* from the network topology rather than assumed
externally. Two strongly-connected neurons end up close; weakly-
connected neurons end up far. The embedding has a clear graph-
theoretic interpretation.

### What it preserves
- Faithful reflection of connectivity-induced clustering.
- 2-D operator applicable on the spectral coordinates.

### What it destroys
- Coordinates depend on the connectivity *snapshot* — embedding
  drifts if synapses plasticise during the run.
- Dynamics-induced separation can leak into the geometry: the
  spectral embedding is computed from `L`, but `L` itself is shaped
  by the same plasticity that drives dynamics. Geometry and dynamics
  are no longer independent.

### Null model
Shuffle-edge null on `L` with degree distribution preserved.

### Failure mode
Plasticity-induced co-evolution of geometry and dynamics. If the
embedding is recomputed mid-run, M is no longer a property of the
trajectory but of the recomputation schedule.

### Required tests
- Verify M-stability under fixed-`L` reads vs recomputed-`L` reads.
- Compare spectral embedding to a graph isomorphism null.

---

## Candidate 4 — Random geometric graph

### Definition
Sample `(x_k, y_k)` i.i.d. from a 2-D distribution (e.g. uniform on
the unit square) **before any dynamics run**, freeze the assignment,
and pass it through the 2-D operator.

### Physical meaning
A null embedding: it imposes geometry without claiming the geometry
matters. Useful only as a null/control, not as a primary candidate.

### What it preserves
- Coordinates are frozen pre-experiment — no risk of post-hoc fit.
- 2-D operator applies directly.

### What it destroys
- Almost everything. There is no physical reason why neuron `k` is
  at `(x_k, y_k)`.

### Null model
This **is** the null model for the other candidates.

### Failure mode
If a candidate (Ring, Sheet, Spectral) does not significantly
out-perform Random Geometric on M, the candidate is not adding
geometric information — its M is indistinguishable from a null
embedding.

### Required tests
- Use it as the null for Candidates 1, 2, 3.

---

## Decision table

| candidate | scientific legitimacy | implementation cost | post-hoc risk | BN-Syn compatibility |
|---|---|---|---|---|
| 1. Ring | low — assumes 1-D phase locality without basis | low (~50 LoC) | medium (free `N` parameter) | poor (random connectivity) |
| 2. 2-D cortical sheet | medium — well-grounded in biology, but BN-Syn currently lacks distance-based coupling | high (~500 LoC, retrofit BN-Syn coupling) | low if `(N_x, N_y)` and Δ are pre-registered | poor *currently*; high if BN-Syn is extended |
| 3. Spectral embedding | high — geometry derived, not assumed | medium (~200 LoC) | medium (snapshot choice) | good (works on existing connectivity) |
| 4. Random geometric | none (null only) | low (~30 LoC) | n/a | n/a |

## Recommendation

- **Primary candidate: Spectral embedding (Candidate 3).** Geometry
  comes from the network's own connectivity, not from an outside
  assumption. The cost is medium; the post-hoc risk is bounded by
  the snapshot-fixing rule. The candidate is compatible with the
  BN-Syn `Network` class as it stands.
- **Fallback: 2-D cortical sheet (Candidate 2).** Higher
  implementation cost and requires retrofitting BN-Syn's
  connectivity, but if the spectral embedding fails its nulls
  (Section "Failure mode"), the cortical sheet provides an
  independent path with a different physical assumption.
- **Always-include null: Random geometric (Candidate 4).**
  Whichever candidate is chosen, this null must run alongside.

## What would falsify the embedding

For Spectral embedding (the primary):

- if M on the spectral embedding is statistically indistinguishable
  from M on the random-geometric null at the same lattice size and
  kernel — embedding adds no information;
- if M values change by more than a pre-registered tolerance under
  re-snapshotting of `L` mid-run — geometry leaks dynamics, the
  embedding is unstable;
- if the operator's HWI sanity bound `H ≤ W₂·√I` fails on this
  embedding (after the JSD-vs-Fisher fix from PR M2.4 candidates) —
  embedding does not rescue the operator.

If any of these three conditions is met on a contracted run, the
embedding path is rejected and the alternative (scale-invariant
operator, PR M2.4) takes precedence in the M2.5 pre-registration.

## What this document is and is not

- It IS a design space for the spatial-embedding path of M2 bridge
  recovery.
- It IS the input to PR M2.5's pre-registration of Path A
  (`BNSYN_2D_SPATIAL_HWI`).
- It is NOT an implementation. No code lives here.
- It is NOT a claim about the substrate. The current status remains
  `OPEN_NARROWED` per `contracts/M_BRIDGE_CLAIM_STATUS.yaml`.
- It does NOT promote `current_status`, mutate the registry, or
  amend any PR #171 contract.
