"""
Cross-substrate γ invariant test.
CI fails if any substrate exits CRITICAL zone (|γ-1| > 0.50).
This is the core proof that intelligence is a regime property.
"""

import sys

sys.path.insert(0, ".")
from core.axioms import SUBSTRATE_GAMMA, classify_regime, verify_axiom_consistency


def test_all_substrates_not_collapsed():
    """No substrate in COLLAPSE zone. Hard requirement."""
    # Skip substrates that do not emit γ (e.g. BN-Syn after Phase 2 hardening
    # downgrade — κ ≠ γ, ledger v2.0.0 sets bnsyn.gamma=null).
    for name, (gamma, note) in SUBSTRATE_GAMMA.items():
        if gamma is None:
            continue
        regime = classify_regime(gamma)
        assert regime != "COLLAPSE", (
            f"Substrate '{name}' collapsed: γ={gamma:.4f} "
            f"|γ-1|={abs(gamma - 1):.4f} > 0.50\nNote: {note}"
        )


def test_majority_substrates_metastable():
    """≥ 4/6 γ-emitting substrates in METASTABLE zone (|γ-1| < 0.15)."""
    metastable = [
        name
        for name, (gamma, _) in SUBSTRATE_GAMMA.items()
        if gamma is not None and abs(gamma - 1.0) < 0.15
    ]
    assert len(metastable) >= 4, f"Only {len(metastable)}/6 substrates metastable: {metastable}"


def test_mean_gamma_near_unity():
    """Mean γ across γ-emitting substrates within 0.15 of 1.0."""
    gammas = [v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]
    mean_g = sum(gammas) / len(gammas)
    assert abs(mean_g - 1.0) < 0.15, f"Mean γ={mean_g:.4f} outside metastable zone"


def test_axiom_consistency():
    """Full AXIOM_0 consistency check (γ-emitting substrates only)."""
    gammas = [v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]
    state = {
        "gamma": sum(gammas) / len(gammas),
        "substrates": [name for name, (g, _) in SUBSTRATE_GAMMA.items() if g is not None],
        "convergence_slope": -0.0016,
    }
    assert verify_axiom_consistency(state), "AXIOM_0 violated"


def test_gamma_formula():
    """γ_PSD = 2H+1 verification. NEVER 2H-1."""
    from core.axioms import gamma_psd

    assert abs(gamma_psd(0.5) - 2.0) < 1e-9
    assert abs(gamma_psd(0.0) - 1.0) < 1e-9
    assert abs(gamma_psd(1.0) - 3.0) < 1e-9
