# Equation traceability index (tool 14)

Machine-readable source: `physics_score.py::EQUATION_TRACE` (checked by
`tests/test_physics_score.py::test_trace_map_files_exist`).

| equation | latex | reference | implemented_in | tested_by | known limits |
|----------|-------|-----------|----------------|-----------|--------------|
| Graph Kuramoto | θ̇ᵢ=ωᵢ+(K/dᵢ)Σwᵢⱼsin(θⱼ−θᵢ−α) | Kuramoto 1984 | dynamics.kuramoto_rhs | test_identical_frequencies_synchronize | mean-field K_c exact only for all-to-all |
| Order parameter | r=\|⟨e^{iθ}⟩\| | Strogatz 2000 | dynamics.order_parameter | test_order_parameter_bounded | — |
| Discrete Ricci flow | w←w(1−εκ), renorm | Ni 2019 | dynamics.ricci_flow | test_ricci_flow_conserves_total_weight | Ollivier curvature is a proxy |
| NFI spectral contract | γ=2H+1 | Flandrin 1989 | spectral.verify_gamma_2h1 | test_gamma_2h1_recovers_hurst | estimator var at small N |
| AdEx | C V̇=−g_L(V−E_L)+g_LΔ_T e^{(V−V_T)/Δ_T}−w+I | Brette-Gerstner 2005 | adex_q10.adex_rhs | test_adex_spikes_under_strong_drive | Euler reset bookkeeping |
| Q10 scaling | τ(T)=τ₀Q10^{(T₀−T)/10} | Bhatt 2010 | adex_q10.q10_scale | test_q10_slows_time_constant_when_cold | applies to τ, not Boltzmann gating |
| Energy balance | dE/dt=P_in−P_diss | — | energy.check_energy_balance | test_adex_energy_balance_quiescent | exact identity in quiescent regime |
| Schnakenberg Jacobian | J at (u*,v*) | Schnakenberg 1979 | turing.schnakenberg_jacobian | test_schnakenberg_turing_unstable_in_known_region | 2-component only |
| Parabolic dt | Δt≤Δx²/(2nD) | Strikwerda 2004 | stability.diffusion_dt_parabolic | test_parabolic_step_scales_as_dx_squared | explicit FTCS |
| Max Lyapunov | Benettin rescaling | Benettin 1980 | stability.max_lyapunov | test_mle_sign_matches_regime | finite-N MLE→0 only as N→∞ |
