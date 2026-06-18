# Falsification register (tool 6)

Every hypothesis carries H0/H1, observable, statistic, rejection rule, failure.
Code: `pf/hypotheses.py`; tests: `tests/physics/test_falsification.py`,
`tests/physics/test_*_nulls.py`.

| id | claim | H0 | H1 | observable | statistic | α/tol | failure (artifact) |
|----|-------|----|----|-----------|-----------|-------|--------------------|
| F-GS-1 | synchronization | r~U(0,1) | r shifted | r(∞) | KS | 0.05 | sync at K≪K_c |
| F-GS-2 | finite-size law | slope=−1/2 | slope≠−1/2 | log r vs log N | OLS slope | 0.12 | wrong scaling |
| F-GS-3 | NFI contract | γ=2H+1 | γ≠2H+1 | PSD slope of r(t) | Welch slope | 0.2 (H) | H not recovered |
| F-MFN-1 | Turing onset | flat spectrum | peak at k_c | spatial PSD | F/t-test | 0.05 | peak without instability |
| F-MFN-2 | diffusion-driven | no instability at D_u=D_v | instability at D_v≫D_u | max growth rate | sign | — | Turing at ratio 1 |
| F-BN-1 | spiking regime | MLE<0 | MLE>0 | Benettin MLE | sign | 1e-2 | chaos labelled stable |

Rule: a positive demonstration is invalid unless its matched null fails first.
