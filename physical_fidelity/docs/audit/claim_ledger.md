# Claim ledger (tool 1)

Each physics claim of the protocol mapped to evidence. NOISE = no carrier.

| claim_id | raw_claim | object | evidence | status |
|----------|-----------|--------|----------|--------|
| C-1 | order parameter bounded [0,1] | Kuramoto r | test_order_parameter_bounded | VERIFIED |
| C-2 | identical freqs synchronize | Kuramoto | test_identical_frequencies_synchronize | VERIFIED |
| C-3 | K=0 incoherent ~1/√N | finite-size law | test_null_k0_incoherent + scaling | VERIFIED |
| C-4 | total graph weight conserved | Ricci flow | test_ricci_flow_conserves_total_weight | VERIFIED |
| C-5 | γ_PSD = 2H+1 | fBm contract | test_gamma_2h1_recovers_hurst | VERIFIED |
| C-6 | AdEx spikes/quiescent | AdEx | test_adex_* | VERIFIED |
| C-7 | Q10 not Boltzmann | thermal | test_q10_slows_time_constant_when_cold | VERIFIED |
| C-8 | energy balance < 1% | open system | test_adex_energy_balance_quiescent | VERIFIED |
| C-9 | Schnakenberg Turing onset | RD-PDE | test_schnakenberg_turing_unstable | VERIFIED |
| C-10 | parabolic dt ≠ CFL | stability | test_parabolic_step_scales_as_dx_squared | VERIFIED |
| C-11 | MLE sign per regime | Lyapunov | test_mle_sign_matches_regime | VERIFIED |
| C-12 | dual-solver L∞ ≤ 1e-4 | replication | test_replication | VERIFIED |
| C-13 | Sobol validated | UQ | test_sobol_matches_ishigami | VERIFIED |
| C-14 | live substrate fidelity 88-92 | GeoSync/BN-Syn/MFN | — | UNKNOWN (apparatus not yet bound — see adversarial_review A1) |
