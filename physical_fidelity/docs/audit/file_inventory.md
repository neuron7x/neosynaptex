# File inventory (Phase 0)

Physics-relevant modules of the verification protocol (the live substrates under
`substrates/{kuramoto,bn_syn,mfn}` are intentionally NOT modified — see
adversarial_review.md for the scope boundary).

| path | mathematical object | equations | tests | risk |
|------|---------------------|-----------|-------|------|
| pf/dynamics.py | graph Kuramoto + Ricci flow | θ̇, r, Ricci | test_protocol, geosync_nulls | curvature proxy |
| pf/spectral.py | fBm spectral contract | γ=2H+1 | test_protocol | estimator variance |
| pf/turing.py | reaction-diffusion | Jacobian, dispersion | mfn_nulls | 2-component |
| pf/adex_q10.py | AdEx + synapses + Q10 | V̇, ẇ, I_syn | bnsyn_nulls, invariants | Euler reset |
| pf/energy.py | open-system balance | dE/dt | invariants | quiescent regime |
| pf/stability.py | dt bounds + Lyapunov | CFL/parabolic, MLE | stability_bounds | — |
| pf/uq.py | parametric UQ | LHS, Sobol | uq_smoke | heavy-tail var |
| pf/hypotheses.py | H0/H1 register | KS, F, scaling | falsification | — |
| pf/dimensional.py | dimensional algebra | homogeneity | dimensional_homogeneity | 4 base units |
| pf/interfaces.py | layer contracts | signal validation | interface_contracts | GeoSync edge only |
| pf/replication.py | dual-solver | RK4 vs DOP853 | replication, convergence | no Julia |
| physics_score.py | 10-axis oracle | S_total | test_physics_score | apparatus-scope |
