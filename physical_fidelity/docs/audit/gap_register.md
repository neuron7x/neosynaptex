# Gap register (NFI-GAP-001 → status)

| gap_id | subsystem | severity | root_cause | patch | status |
|--------|-----------|----------|-----------|-------|--------|
| GAP-O-01 | all | CRITICAL | no scoring oracle/baseline | physics_score.py + metrics_schema.json | CLOSED |
| GAP-O-02 | GeoSync | CRITICAL | Kuramoto/Ricci uncoupled | dynamics.py (Kuramoto fixed, Ricci=weight layer) | CLOSED |
| GAP-O-03 | all | CRITICAL | no interface contracts | interfaces.py + docs | CLOSED (GeoSync edge tested; A5) |
| GAP-M-01 | BN-Syn | CRITICAL | Boltzmann in AdEx | Q10 path; Boltzmann forbidden | CLOSED |
| GAP-M-03 | MFN | MAJOR | Turing not operationalized | turing.py Jacobian+onset | CLOSED |
| GAP-M-04 | MFN | MODERATE | CFL on parabolic PDE | diffusion_dt_parabolic | CLOSED |
| GAP-M-05 | all | MAJOR | MLE targets inverted | regime-conditioned classifier | CLOSED |
| GAP-E-01 | MFN | CRITICAL | MC without stochasticity | uq.py prior + LHS + Sobol | CLOSED |
| GAP-E-02 | all | MAJOR | tests without H0 | hypotheses.py register | CLOSED |
| GAP-E-06 | all | MODERATE | no independent replication | replication.py | CLOSED (no Julia; A4) |
| GAP-P-03 | all | MAJOR | energy balance undefined | energy.py exact identity | CLOSED |
| GAP-C-01 | GeoSync | MAJOR | γ=2H+1 untested | spectral.verify_gamma_2h1 | CLOSED |
| GAP-NEW | all | OPEN | apparatus not bound to live substrates | Phase-8 binding layer | OPEN (A1) |
