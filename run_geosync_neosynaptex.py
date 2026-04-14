#!/usr/bin/env python3
"""Run neosynaptex with GeoSync Market adapter.

Usage:
    cd /path/to/neosynaptex
    python run_geosync_neosynaptex.py
"""

import sys

sys.path.insert(0, ".")

from neosynaptex import MockBnSynAdapter, MockMfnAdapter, Neosynaptex

from substrates.geosync_market.adapter import GeoSyncMarketAdapter

print("=" * 60)
print("  NEOSYNAPTEX + GEOSYNC LIVE ")
print("=" * 60)
print()

print("Loading market data (120d) ...")
nx = Neosynaptex(window=16)
nx.register(MockBnSynAdapter())
nx.register(MockMfnAdapter())

try:
    nx.register(GeoSyncMarketAdapter(lookback_days=120))
    market_active = True
    print("  geosync_market: registered")
except Exception as e:
    print(f"  market adapter failed: {e}")
    print("  running without market substrate")
    market_active = False

print()
print("Running 30 ticks ...")
s = None
for i in range(30):
    s = nx.observe()

if s is None:
    print("ERROR: no observations collected")
    sys.exit(1)

print()
print("=" * 60)
print("  RESULTS ")
print("=" * 60)
print(f"gamma_mean      = {round(s.gamma_mean, 4)}")
print(f"phase           = {s.phase}")
print(f"cross_coherence = {round(s.cross_coherence, 4)}")
print(f"spectral_radius = {round(s.spectral_radius, 4)}")
print(f"resilience      = {round(s.resilience_score, 4)}")
print()
print("gamma per domain:")
for d, g in sorted(s.gamma_per_domain.items()):
    if g != g:  # nan
        flag = "(nan)"
    elif abs(g - 1.0) < 0.15:
        flag = "✓ METASTABLE"
    elif abs(g - 1.0) < 0.30:
        flag = "~ MARGINAL"
    else:
        flag = "✗ OUTSIDE"
    print(f"  {d:20s} gamma={g:+.4f}  {flag}")

proof = nx.export_proof()
print()
print(f"verdict         = {proof.get('verdict')}")
print()

# Trading filter:
# Fire only when the full system is coherent AND phase is metastable
if s.phase == "METASTABLE" and proof.get("verdict") == "COHERENT":
    print("TRADING FILTER: ACTIVE — Ricci signal confirmed by NFI")
else:
    reason_phase = s.phase if s.phase != "METASTABLE" else None
    reason_verdict = proof.get("verdict") if proof.get("verdict") != "COHERENT" else None
    reasons = [r for r in (reason_phase, reason_verdict) if r]
    print(f"TRADING FILTER: SUPPRESSED — {' / '.join(reasons) if reasons else 'system not coherent'}")

print()
if market_active:
    print("NOTE: geosync_market substrate was active in this run.")
else:
    print("NOTE: geosync_market substrate was NOT active (data load failed).")
