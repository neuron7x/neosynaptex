# BN-Syn — canonical mathematical object

Canonical object: **AdEx + conductance synapses**. Code `pf/adex_q10.py`.

## AdEx membrane

```
C · dV/dt = −g_L(V − E_L) + g_L Δ_T exp((V − V_T)/Δ_T) − w + I_syn + I_ext
τ_w · dw/dt = a(V − E_L) − w
```

State vector: `(V [mV], w [pA], g_e [nS], g_i [nS])`.
Code `adex_rhs`; defaults `AdExParams` (Brette & Gerstner 2005 regular-spiking).

## Conductance synapses

```
I_syn = −g_e(t)(V − E_e) − g_i(t)(V − E_i)
dg_e/dt = −g_e/τ_e   (+ δ-impulse at spike arrival)
dg_i/dt = −g_i/τ_i
```

Code `SynapseParams`, `simulate_adex_energy`.

## Temperature — Q10 ONLY (Boltzmann FORBIDDEN)

```
τ_w(T) = τ_w(T₀) · Q10^((T₀ − T)/10)        Q10 ≈ 2–3 (Bhatt et al. 2010)
```

The Boltzmann channel-gating factor `exp(−E/kT)` is a **category error** in AdEx:
AdEx (Brette & Gerstner 2005) already integrated out HH channel gating; Δ_T
encodes onset sharpness at fixed temperature. `q10_scale` is the only thermal path.
NB: the existing `substrates/bn_syn` temperature *schedule* is an annealing control
signal, not physical temperature — it is left untouched.

## Energy proxy (exact identity, GAP-P-03)

With E = ½ C (V−E_L)², the chain rule gives the *exact* open-system balance

```
dE/dt = −g_L(V−E_L)²  +  (V−E_L)[g_L Δ_T exp(.) − w + I_ext + I_syn]
P_diss = g_L(V−E_L)²            (leak dissipation)
P_input = (V−E_L)[ … bracket … ]
Test (quiescent): |∫(P_input − P_diss)dt − ΔE| / scale < 1%
```

Code `simulate_adex_energy` + `pf/energy.py::check_energy_balance`;
test `tests/physics/test_invariants.py::test_adex_energy_balance_quiescent`.

## Lyapunov expectations
quiescent regime: MLE < 0; spiking regime: MLE > 0 — verified separately.

## References
Brette & Gerstner 2005; Bhatt et al. 2010.
