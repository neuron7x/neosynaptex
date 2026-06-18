# Adversarial review (tool 13) — attack on this protocol

The critic attacks its own deliverable. Findings are ranked by how badly they
would mislead a reader who trusts the green checkmarks.

## A1 — CRITICAL: the score measures the apparatus, not the live substrates
`physics_score.py` scores the *reference verification apparatus* in `pf/` and the
*existence + passing* of the protocol's own deliverables. It does **not** call
into `substrates/kuramoto`, `substrates/bn_syn`, or `substrates/mfn` production
code. Therefore **S_total = 100 is an apparatus-admissibility number, not a
GeoSync/BN-Syn/MFN physical-fidelity number.** The NFI-PROMPT-002 target band
[88, 92] was framed for the live substrates; it does not apply to a complete,
correct reference apparatus, which scores 100 by construction.
- Evidence: every `score_*` fn in `physics_score.py` imports only `pf.*`.
- Required action: a Phase-8 binding layer that wires each verifier to the real
  substrate APIs and re-measures. That number will be < 100 and is the only one
  that answers "is the repo at physical rank 88-92".
- Status: **disclosed**, not hidden — see `baseline_report.md` and `VERDICT.md`.

## A2 — MAJOR: high scores come from self-consistent reference physics
The analytic references (K_c, γ=2H+1, Schnakenberg, RK4 order) are verified
against closed forms that the same author encoded. This proves internal
correctness (the code reproduces the textbook), not external validity of any
research claim. Mitigated by: adversarial tests that must FAIL on white noise,
equal diffusion, below-K_c, σ=0 UQ — these catch a verifier that always says yes.

## A3 — MODERATE: Ollivier curvature is a proxy
`ollivier_lin_curvature` uses common-neighbour counts, not an optimal-transport
solve. The conservation invariant (Σw) is exact regardless, but curvature *values*
are approximate. Flagged in code and `geosync_core.md`.

## A4 — MODERATE: no Julia third solver
Independent replication is RK4 vs SciPy DOP853 (two methods, one language). True
language independence (Julia) is absent. rel L∞ = 2.3e-09 is strong but within one
ecosystem. Disclosed in `reference_solvers/README.md`.

## A5 — MINOR: interface contract validated on one edge
Only GeoSync→BN-Syn output is validated against a live signal; BN-Syn→MFN and
MFN→conclusion contracts are specified but not yet signal-tested.

## Tests that could pass by accident — checked
- KS synchronization test: guarded by N=15 repeats + adversarial below-K_c test.
- Sobol: validated against the analytic Ishigami benchmark, not self-reference.
- Energy balance: exact identity, residual 2.8e-4 ≪ 1e-2 threshold (real margin).
