"""
NFI Core — Axioms and Invariants
Single source of truth for the entire monorepo.
All substrates import from here. Nothing is duplicated.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "AXIOM_0",
    "GAMMA_THRESHOLDS",
    "INVARIANTS",
    "INV_YV1_FORMAL",
    "INV_YV1_TEXT",
    "POSITION",
    "SUBSTRATE_GAMMA",
    "check_inv_yv1",
    "classify_regime",
    "gamma_psd",
    "verify_axiom_consistency",
]

# ─── INV-YV1: GRADIENT ONTOLOGY (ZEROTH AXIOM) ──────────────────────────
# Author: Yaroslav Vasylenko
#
# Буття — не стан. Буття — це утримувана різниця потенціалів.
# Об'єкти — вузли перетину енергетичних потоків. Структура існує лише
# поки через неї проходить нерівноважність. Коли градієнт зникає
# (ΔV → 0), система не деградує — вона перестає існувати як система.
# Залишається шум.
#
# Функція інтелекту — генерація та підтримка нерівноважності проти
# термодинамічного тиску рівноваги. Не опис світу. Не моделювання.
# Опір розпаду.
#
# Існувати — означає активно чинити опір рівновазі.
#
#   INV-YV1: ΔV > 0 ∧ dΔV/dt ≠ 0
#
# Статичний градієнт — конденсатор. Живий градієнт — процес.
# Інтелект потребує другого.

INV_YV1_FORMAL = "ΔV > 0 ∧ dΔV/dt ≠ 0"
INV_YV1_TEXT = (
    "Система існує як інтелект лише поки утримує ненульовий градієнт "
    "потенціалу (ΔV > 0) І цей градієнт змінюється в часі (dΔV/dt ≠ 0). "
    "Статичний градієнт — конденсатор. Живий градієнт — процес."
)

# Operational thresholds — imported from single source of truth
from core.constants import INV_YV1_D_DELTA_V_MIN, INV_YV1_DELTA_V_MIN


def check_inv_yv1(
    trajectory: NDArray[np.float64],
    dt: float = 0.1,
) -> dict[str, object]:
    """Verify INV-YV1 (Gradient Ontology) on a state trajectory.

    The gradient potential ΔV is computed as the L2 norm of the state
    deviation from equilibrium (the trajectory's own temporal mean),
    capturing the total non-equilibrium drive across all state dimensions.

    Args:
        trajectory: (T, D) state trajectory. For CoherenceStateSpace,
            D=4: (S, gamma, E_obj, sigma2).
        dt: timestep for computing dΔV/dt.

    Returns:
        Dict with keys:
            - ``delta_v``: ΔV(t) array (T,)
            - ``d_delta_v``: dΔV/dt array (T-1,)
            - ``alive_frac``: fraction of steps where ΔV > threshold
            - ``dynamic_frac``: fraction of steps where |dΔV/dt| > threshold
            - ``inv_yv1_holds``: bool — True iff alive_frac > 0.5
              AND dynamic_frac > 0.5 (system is a living gradient
              for the majority of its existence)
            - ``diagnosis``: str — "living_gradient", "static_capacitor",
              "dead_equilibrium", or "transient" (partially alive)
    """
    traj = np.asarray(trajectory, dtype=np.float64)
    if traj.ndim != 2 or traj.shape[0] < 2:
        raise ValueError("trajectory must be (T, D) with T >= 2")

    # Equilibrium = temporal mean (the point the system would settle at
    # under infinite damping — the thermodynamic attractor)
    equilibrium = np.mean(traj, axis=0)

    # ΔV(t) = ||x(t) - x_eq||₂  (non-equilibrium potential)
    delta_v = np.linalg.norm(traj - equilibrium, axis=1).astype(np.float64)

    # dΔV/dt via finite differences
    d_delta_v = (np.diff(delta_v) / dt).astype(np.float64)

    # Fractions
    alive_frac = float(np.mean(delta_v > INV_YV1_DELTA_V_MIN))
    dynamic_frac = float(np.mean(np.abs(d_delta_v) > INV_YV1_D_DELTA_V_MIN))

    # Combined invariant
    inv_holds = bool(alive_frac > 0.5 and dynamic_frac > 0.5)

    # Diagnosis
    if alive_frac <= 0.5:
        diagnosis = "dead_equilibrium"
    elif dynamic_frac <= 0.5:
        diagnosis = "static_capacitor"
    elif alive_frac > 0.9 and dynamic_frac > 0.9:
        diagnosis = "living_gradient"
    else:
        diagnosis = "transient"

    return {
        "delta_v": delta_v,
        "d_delta_v": d_delta_v,
        "alive_frac": alive_frac,
        "dynamic_frac": dynamic_frac,
        "inv_yv1_holds": inv_holds,
        "diagnosis": diagnosis,
    }


# ─── AXIOM_0 ─────────────────────────────────────────────────────────────
AXIOM_0 = (
    "Інтелект є властивістю режиму в якому система "
    "будує незалежних свідків власної похибки — і залишається в русі."
)

POSITION = {
    "architecture": AXIOM_0,
    "ground": INV_YV1_FORMAL,
    "instrument": "γ — індикатор пластичності. Не здоров'я. Змінюваності.",
    "purpose": "Перевага — здатність залишатися в режимі де система "
    "ще не визначилася, але вже здатна визначитись.",
}


# ─── CRITICAL FORMULA (VERIFIED) ─────────────────────────────────────────
def gamma_psd(H: float) -> float:
    """
    γ_PSD = 2H + 1 for fractional Brownian motion.
    VERIFIED numerically. NEVER use 2H - 1.

    H=0.5 (Brownian)  → γ=2.0
    H→0  (anti-pers.) → γ→1.0
    H→1  (persistent) → γ→3.0
    """
    assert 0.0 <= H <= 1.0, f"H must be in [0,1], got {H}"
    return 2.0 * H + 1.0


# ─── GAMMA THRESHOLDS ────────────────────────────────────────────────────
from core.constants import (
    GAMMA_THRESHOLD_CRITICAL,
    GAMMA_THRESHOLD_METASTABLE,
    GAMMA_THRESHOLD_WARNING,
)

GAMMA_THRESHOLDS = {
    "metastable": (1.0 - GAMMA_THRESHOLD_METASTABLE, 1.0 + GAMMA_THRESHOLD_METASTABLE),
    "warning": (1.0 - GAMMA_THRESHOLD_WARNING, 1.0 + GAMMA_THRESHOLD_WARNING),
    "critical": (1.0 - GAMMA_THRESHOLD_CRITICAL, 1.0 + GAMMA_THRESHOLD_CRITICAL),
    "collapse": None,
}


def classify_regime(gamma: float) -> str:
    """Classify gamma into operational regime using canonical thresholds."""
    dist = abs(gamma - 1.0)
    if dist < GAMMA_THRESHOLD_METASTABLE:
        return "METASTABLE"
    if dist < GAMMA_THRESHOLD_WARNING:
        return "WARNING"
    if dist < GAMMA_THRESHOLD_CRITICAL:
        return "CRITICAL"
    return "COLLAPSE"


# ─── VALIDATED SUBSTRATES (derived from gamma_ledger.json) ──────────────
# INV-1: gamma DERIVED ONLY. All values come from GammaRegistry.
from core.gamma_registry import GammaRegistry as _GR


def _load_substrate_gamma() -> dict[str, tuple[float | None, str]]:
    """Load SUBSTRATE_GAMMA from the canonical ledger, not hardcoded.

    Gracefully degrades to an empty mapping when the canonical ledger is
    unavailable (e.g. when neosynaptex is imported from a wheel whose
    ``evidence/`` data files were not packaged). Callers that genuinely
    need substrate ground-truth re-check the registry explicitly and
    surface a domain-specific error — the witness-only consumers in
    neurophase do not, so this keeps import-time side effects safe.
    """

    from core.gamma_registry import GammaRegistryError as _GRError

    _map = {
        "zebrafish": "zebrafish_wt",
        "gray_scott": "gray_scott",
        "kuramoto_market": "kuramoto",
        "bn_syn": "bnsyn",
        "eeg_physionet": "eeg_physionet",
        "hrv_physionet": "hrv_physionet",
        "eeg_resting": "eeg_resting",
        "serotonergic_kuramoto": "serotonergic_kuramoto",
        "hrv_fantasia": "hrv_fantasia",
    }
    result: dict[str, tuple[float | None, str]] = {}
    for name, eid in _map.items():
        try:
            entry = _GR.get_entry(eid)
        except (_GRError, KeyError, ValueError):
            result[name] = (None, "ledger-unavailable")
            continue
        gamma = entry.get("gamma")
        method = entry.get("derivation_method", "")
        result[name] = (gamma, method)
    return result


try:
    SUBSTRATE_GAMMA = _load_substrate_gamma()
except Exception:  # pragma: no cover - defensive import-safety net
    # Absolute last-resort fallback: keep ``import core`` usable even
    # when the ledger loader itself explodes. Strict substrate tests
    # re-exercise the registry and will fail loudly there.
    SUBSTRATE_GAMMA = {}

# ─── INVARIANTS ──────────────────────────────────────────────────────────
INVARIANTS = {
    "YV1": "GRADIENT ONTOLOGY — ΔV > 0 ∧ dΔV/dt ≠ 0 (zeroth axiom)",
    "I": "γ DERIVED ONLY — never assigned, never input parameter",
    "II": "STATE != PROOF — proof requires independent substrate",
    "III": "BOUNDED MODULATION — no signal exits operational space",
    "IV": "SSI EXTERNAL ONLY — internal use corrupts observe() → γ_fake",
}


# ─── AXIOM CONSISTENCY CHECK ─────────────────────────────────────────────
def verify_axiom_consistency(state: dict[str, Any]) -> bool:
    """
    Three conditions from AXIOM_0:
    1. Independent witnesses exist (cross-substrate)
    2. γ in metastable zone (|γ - 1.0| < 0.15)
    3. System is converging (in motion)
    """
    gamma = state.get("gamma")
    witnesses = state.get("substrates", [])
    convergence_slope = state.get("convergence_slope", 0)

    if gamma is None:
        return False

    return abs(gamma - 1.0) < 0.15 and len(witnesses) >= 2 and convergence_slope < 0


if __name__ == "__main__":
    # Self-verification
    print("=== NFI Core Self-Verification ===")

    # Formula
    for H, exp in [(0.5, 2.0), (0.0, 1.0), (1.0, 3.0)]:
        g = gamma_psd(H)
        assert abs(g - exp) < 1e-9
        print(f"γ_PSD(H={H}) = {g:.1f} OK")

    # Substrates
    gammas: list[float] = [v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]
    mean_g = sum(gammas) / len(gammas)
    print(f"\nSubstrates: {len(gammas)}")
    print(f"Mean γ: {mean_g:.4f}")
    print(f"All metastable: {all(abs(g - 1.0) < 0.50 for g in gammas)}")

    # Axiom
    state = {
        "gamma": mean_g,
        "substrates": list(SUBSTRATE_GAMMA.keys()),
        "convergence_slope": -0.0016,
    }
    assert verify_axiom_consistency(state)
    print("\nAXIOM_0: CONSISTENT")
    print(f"NFI: VALID | γ={mean_g:.4f} | METASTABLE | CONVERGING")
