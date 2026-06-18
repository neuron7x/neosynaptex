# Units table (dimensional homogeneity, tool 3)

Verified symbolically in `pf/dimensional.py`; tested in
`tests/physics/test_dimensional_homogeneity.py`. Base units (kg, m, s, A).

| equation | every additive term reduces to | homogeneous |
|----------|-------------------------------|:-----------:|
| Kuramoto dθ/dt = ω + (K/N)Σ sin | angular rate [1/s] | ✅ |
| AdEx C dV/dt = −g_L(V−E_L)+… | current [A] (pA scale) | ✅ |
| Reaction-diffusion ∂_t u = DΔu+f | concentration rate [u]/s | ✅ |
| Energy dE/dt = P_in − P_diss | power [W] | ✅ |

| symbol | quantity | unit |
|--------|----------|------|
| V | membrane voltage | mV |
| w | adaptation current | pA |
| g_L, g_e, g_i | conductance | nS |
| C | capacitance | pF |
| K | coupling | 1/s |
| ω | natural frequency | 1/s |
| θ | phase | rad (dimensionless) |
| D_u, D_v | diffusion | m²/s |
| u, v | concentration | mol/m³ |
