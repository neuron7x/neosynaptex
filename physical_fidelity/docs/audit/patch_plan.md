# Patch plan (tool 12)

| phase | file | change | test | acceptance gate |
|-------|------|--------|------|-----------------|
| done | pf/dynamics.py | Kuramoto + Ricci conservation | test_protocol | r∈[0,1], Σw conserved |
| done | pf/spectral.py | γ=2H+1 round-trip | test_gamma_2h1 | |H_rec−H|<0.12 |
| done | pf/turing.py | Schnakenberg onset | test_mfn_nulls | unstable@40, stable@1 |
| done | pf/adex_q10.py | AdEx+synapses+Q10 | test_invariants | energy<1% |
| done | physics_score.py | 10-axis oracle | test_physics_score | S∈[0,100] computed |
| OPEN | pf/bind_substrates.py (Phase 8) | wire verifiers to substrates/* | test_substrate_binding | live S measured |
