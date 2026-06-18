# MFN⁺ — canonical mathematical object

Canonical object: **two-component reaction–diffusion PDE** (Schnakenberg
instance). Code `pf/turing.py`.

## Fields

```
∂_t u = D_u Δu + f(u, v)
∂_t v = D_v Δv + g(u, v)
```

Reaction terms (Schnakenberg 1979), defined explicitly:

```
f(u, v) = a − u + u² v
g(u, v) = b − u² v
```

## Homogeneous steady state + Jacobian

```
u* = a + b,        v* = b / (a + b)²
J = [[f_u, f_v],[g_u, g_v]] at (u*, v*):
  f_u = −1 + 2u*v* = (b−a)/(a+b)
  f_v = u*² = (a+b)²
  g_u = −2u*v* = −2b/(a+b)
  g_v = −u*² = −(a+b)²
```

Code `schnakenberg_steady_state`, `schnakenberg_jacobian`.

## Turing instability (computable, not declarative)

```
(T1) tr J < 0,  (T2) det J > 0              (stable without diffusion)
(T3) D_v f_u + D_u g_v > 0
(T4) (D_v f_u + D_u g_v)² > 4 D_u D_v det J
k_c² = sqrt(det J / (D_u D_v))              (critical wavenumber)
```

Code `analyze_turing` / `analyze_schnakenberg`; critical ratio
`critical_diffusion_ratio`. Tests `test_schnakenberg_turing_unstable_in_known_region`,
`test_equal_diffusion_no_turing_adversarial`.

## Stability (parabolic — NOT CFL, GAP-M-04)

```
explicit FTCS:  Δt ≤ Δx² / (2 · n_dim · D_max)
```

CFL (`Δt ≤ Δx/c`) applies only to hyperbolic terms, if any. Code
`pf/stability.py::diffusion_dt_parabolic` vs `cfl_dt_hyperbolic`; the two scale
differently (Δx² vs Δx) — test `test_parabolic_step_scales_as_dx_squared`.

## References
Turing 1952; Murray 2003 Ch.2; Schnakenberg 1979; Strikwerda 2004.
