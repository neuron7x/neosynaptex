# Reference (secondary) solvers

Primary solver: hand-rolled fixed-step RK4 (`pf/dynamics.py::integrate_kuramoto`).
Secondary independent solver: SciPy adaptive **DOP853** driven on the *same vector
field* (`pf/replication.py::independent_replication`). Agreement requirement:
relative L∞ ≤ 1e-4 on the canonical scenario (N=10 oscillators, T=100s).

Julia `DifferentialEquations.jl` is the protocol's preferred third path but is not
installed in this environment; the NumPy/SciPy independent integrator is the
sanctioned fallback (NFI-PROMPT-002 §5.D). Measured: rel L∞ = 2.3e-09 (PASS).
