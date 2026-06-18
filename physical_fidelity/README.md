# physical_fidelity — NFI executable VVUQ protocol

Closes the gaps of **NFI-GAP-001** and implements **NFI-PROMPT-002**: converts the
audited *Physical Fidelity Plan v1.0* from a proposal template into an executable,
falsifiable verification protocol (ASME V&V 10-2019).

> **Classification: ADMISSIBILITY.** Nothing here is a science claim or a
> validation of the live GeoSync/BN-Syn/MFN substrates. It verifies that the
> reference apparatus reproduces known physics and that the protocol deliverables
> exist and pass. See `baseline_report.md` for the honest reading of S₀.

## Layout

```
pf/                     reference physics + verifiers (pure, cited, typed)
  dynamics.py           graph Kuramoto + normalized discrete Ricci flow (GAP-O-02)
  spectral.py           gamma_PSD = 2H+1 round-trip (GAP-C-01)
  turing.py             Schnakenberg Jacobian + Turing onset (GAP-M-03)
  adex_q10.py           AdEx + conductance synapses + Q10, NO Boltzmann (GAP-M-01/02)
  energy.py             open-system energy balance (GAP-P-03)
  stability.py          parabolic vs hyperbolic dt + Lyapunov (GAP-M-04/05)
  uq.py                 lognormal prior, LHS, Saltelli Sobol (GAP-E-01)
  hypotheses.py         H0/H1 register: KS, F-test, scaling (GAP-E-02)
  dimensional.py        symbolic dimensional homogeneity (GAP-P-01)
  interfaces.py         inter-layer contracts (GAP-O-03)
  replication.py        RK4 vs SciPy DOP853, convergence (GAP-E-06)
  scoring.py            admissibility ScoreCard primitives (GAP-O-01)
  baseline.py           10-metric reference baseline
physics_score.py        10-axis oracle S_total (NFI-PROMPT-002 §1)
metrics_schema.json     axis weights / thresholds / targets
baseline_report.md      honest S0 report
docs/physics/*.md       canonical math object specs (one decision per subsystem)
tests/                  falsifiable + adversarial proofs
tests/physics/          null models, convergence, invariants, contracts
reproducibility/        manifest.json + run_physics_validation.sh
```

## Run

```bash
bash physical_fidelity/reproducibility/run_physics_validation.sh
# or piecewise:
python -m physical_fidelity.physics_score      # S_total
python -m physical_fidelity.pf.baseline        # reference S0
python -m pytest physical_fidelity/tests/ -q   # falsifiable suite
```

## Design rules honored

- Every claim has equation | code_path | test | metric | baseline | citation.
- Null models are implemented first; positive demonstrations require a rejected
  null (adversarial tests assert the verifiers fail on white noise, equal
  diffusion, below-K_c).
- One canonical math object per subsystem, fixed in `docs/physics/` before code.
- Score is never tuned to a target band; reported as measured.
```
claim_status: measured
```
