#!/usr/bin/env python3
"""neosynaptex demo -- all admissible substrates (mode="demo").

Sibling to ``demo_real.py``. Where ``demo_real`` enforces
``mode="real"`` (only REAL + ADMISSIBLE substrates pass the
registration gate), this demo uses the permissive ``mode="demo"`` so
that synthetic simulations can be exercised alongside real data for
cross-substrate diagnostics and smoke tests.

Registered here:

* Zebrafish (real, admissible)
* Gray-Scott (synthetic, admissible)
* Kuramoto (synthetic, admissible)
* BN-Syn (synthetic, admissible)

The CNS-AI substrate is deliberately absent; its claim_status is
``downgraded`` and it has no place in either demo.
"""

import os

import numpy as np

from neosynaptex import Neosynaptex
from substrates.bn_syn.adapter import BnSynAdapter
from substrates.gray_scott.adapter import GrayScottAdapter
from substrates.kuramoto.adapter import KuramotoAdapter
from substrates.zebrafish.adapter import ZebrafishAdapter


def _f(v: float, w: int = 6) -> str:
    return f"{v:.3f}".rjust(w) if np.isfinite(v) else "n/a".rjust(w)


def main() -> None:
    nx = Neosynaptex(window=16, mode="demo")

    # Admissible substrates across real + synthetic provenance.
    # Zebrafish requires local data files; on CI runners where those
    # files are absent, degrade gracefully to synthetic-only demo so
    # pipeline smoke checks remain deterministic.
    nx.register(ZebrafishAdapter("WT"))
    nx.register(GrayScottAdapter())
    nx.register(KuramotoAdapter())
    nx.register(BnSynAdapter())

    allow_synthetic_fallback = os.getenv("NEOSYNAPTEX_DEMO_SYNTHETIC_ONLY") == "1"
    try:
        s = nx.observe()
    except RuntimeError as exc:
        if "Cannot load zebrafish data" not in str(exc) or not allow_synthetic_fallback:
            raise
        print("WARN: zebrafish data missing; running explicit synthetic-only demo mode.")
        nx = Neosynaptex(window=16, mode="demo")
        nx.register(GrayScottAdapter())
        nx.register(KuramotoAdapter())
        nx.register(BnSynAdapter())
        s = nx.observe()
    for _ in range(49):
        s = nx.observe()
        print(
            f"  t={s.t:02d}  "
            f"gamma={_f(s.gamma_mean)}  "
            f"dg/dt={_f(s.dgamma_dt)}  "
            f"sr={_f(s.spectral_radius)}  "
            f"coh={_f(s.cross_coherence)}  "
            f"p={_f(s.universal_scaling_p)}  "
            f"phase={s.phase}"
        )

    print()
    print("=" * 72)
    print("  NEOSYNAPTEX -- MULTI-SUBSTRATE DEMO (mode=demo)")
    print("=" * 72)
    print(f"  gamma_mean       = {_f(s.gamma_mean)}")
    print(f"  gamma_std        = {_f(s.gamma_std)}")
    print(f"  dgamma/dt        = {_f(s.dgamma_dt)}")
    print(f"  cross_coherence  = {_f(s.cross_coherence)}")
    print(f"  universal_p      = {_f(s.universal_scaling_p)}")
    print(f"  spectral_radius  = {_f(s.spectral_radius)}")
    print(f"  phase            = {s.phase}")
    print(f"  resilience       = {_f(s.resilience_score)}")
    print()

    for d in sorted(s.gamma_per_domain):
        g = s.gamma_per_domain[d]
        ci = s.gamma_ci_per_domain[d]
        sr = s.sr_per_domain.get(d, float("nan"))
        anom = s.anomaly_score.get(d, float("nan"))
        mod = s.modulation.get(d, 0.0)
        ci_str = f"[{_f(ci[0], 5)}, {_f(ci[1], 5)}]" if np.isfinite(ci[0]) else "[n/a]"
        print(
            f"  {d:12s}  "
            f"g={_f(g, 6)}  "
            f"CI={ci_str}  "
            f"sr={_f(sr, 6)}  "
            f"anom={_f(anom, 5)}  "
            f"mod={mod:+.4f}"
        )

    print()
    proof = nx.export_proof()
    print(f"  Verdict: {proof.get('verdict')}")
    print("=" * 72)


if __name__ == "__main__":
    main()
