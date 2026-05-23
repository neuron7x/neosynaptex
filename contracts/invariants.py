"""NFI Invariant Enforcement — runtime contracts for system integrity.

AXIOM_0: Intelligence is a property of the regime in which a system
builds independent witnesses of its own error — and remains in motion.

All invariants are consequences of AXIOM_0. No exceptions.

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any


class SSIDomain(Enum):
    """SSI operational domain."""

    EXTERNAL = "external"  # valid: market, multi-agent, boundary
    INTERNAL = "internal"  # FORBIDDEN: corrupts observe() -> gamma_fake


class InvariantViolation(Exception):
    """Raised when any NFI invariant is violated.

    An invariant violation is not a recoverable error.
    It indicates architectural corruption that invalidates
    all downstream gamma derivations.
    """

    pass


# ---------------------------------------------------------------------------
# INVARIANT_IV: SSI DOMAIN = EXTERNAL ONLY
# ---------------------------------------------------------------------------
def ssi_enforce_domain(domain: SSIDomain) -> None:
    """Gate: raise InvariantViolation if domain is INTERNAL.

    SSI is the skin of the organism -- not inside, not outside, on the boundary.
    Internal self-obfuscation contaminates observe() input,
    causing gamma to be derived from constructed signal instead of true state.

    dzerkalo.py begins reflecting not the system state,
    but a constructed signal. gamma is computed from corrupted input.
    Two stacks in one machine without isolation = verification collapse.
    """
    if domain == SSIDomain.INTERNAL:
        raise InvariantViolation(
            "INVARIANT_IV VIOLATED: SSI cannot operate on internal NFI state.\n"
            "Reason: observe(constructed_signal) -> gamma_fake corrupts architecture.\n"
            "Internal verification requires independent substrate: BN-Syn, zebrafish.\n"
            "SSI domain must be EXTERNAL only. See AXIOM_0."
        )


def ssi_apply(signal: Any, domain: SSIDomain, transform: Callable[..., Any] | None = None) -> Any:
    """Apply SSI transformation to signal with domain enforcement.

    Args:
        signal:    raw input signal from external source
        domain:    SSIDomain.EXTERNAL (valid) or SSIDomain.INTERNAL (forbidden)
        transform: optional callable to apply to validated signal

    Returns:
        Transformed signal if domain is EXTERNAL.

    Raises:
        InvariantViolation: if domain is INTERNAL.
    """
    ssi_enforce_domain(domain)
    if transform is not None:
        return transform(signal)
    return signal


# ---------------------------------------------------------------------------
# INVARIANT_I: GAMMA DERIVED ONLY
# ---------------------------------------------------------------------------
def enforce_gamma_derived(gamma_source: str) -> None:
    """Gate: gamma must come from computation, never assignment.

    gamma is a signature of the regime, not a metric to be set.
    If gamma is assigned externally, INVARIANT_I is violated.
    """
    forbidden_sources = {"manual", "assigned", "target", "constant", "hardcoded"}
    if gamma_source.lower() in forbidden_sources:
        raise InvariantViolation(
            f"INVARIANT_I VIOLATED: gamma source '{gamma_source}' is forbidden.\n"
            "gamma must be derived from observe() -> theilslopes() -> value.\n"
            "Never assigned, never a target, never an input parameter."
        )


def enforce_state_not_proof(state_source: str, proof_source: str) -> None:
    """Gate: state and proof must come from independent sources.

    A system cannot be an independent witness of itself.
    BN-Syn verifies what NFI cannot verify alone.
    """
    if state_source == proof_source:
        raise InvariantViolation(
            f"INVARIANT_II VIOLATED: state and proof share source '{state_source}'.\n"
            "Proof requires independent substrate (BN-Syn, zebrafish, etc.).\n"
            "A system is not an independent witness of itself."
        )


# ---------------------------------------------------------------------------
# INVARIANT_III: BOUNDED MODULATION
# ---------------------------------------------------------------------------
# Contracts layer is self-contained — no imports from core to avoid cycles.
# These values MUST match core.constants (tested in CI invariant checks).
_MODULATION_BOUND = 0.05


def enforce_bounded_modulation(modulation: float) -> float:
    """Gate: clamp modulation to [-0.05, +0.05].

    Unbounded modulation collapses the regime.
    Returns clamped value (never raises -- clamps instead).
    """
    return max(-_MODULATION_BOUND, min(_MODULATION_BOUND, modulation))


# ---------------------------------------------------------------------------
# GAMMA THRESHOLD SPECIFICATION
# ---------------------------------------------------------------------------
# Self-contained — canonical values duplicated here to avoid circular import.
# core.constants holds the same values for core/ modules.
GAMMA_THRESHOLDS = {
    "metastable": (0.85, 1.15),
    "warning": (0.70, 1.30),
    "critical": (0.50, 1.50),
}


def gamma_regime(gamma: float) -> str:
    """Re-export canonical classify_regime from axioms (lazy to avoid circular import)."""
    from core.axioms import classify_regime

    return classify_regime(gamma)


# ---------------------------------------------------------------------------
# INVARIANT_YV1: GRADIENT ONTOLOGY (ZEROTH — above all others)
# ---------------------------------------------------------------------------
def enforce_gradient_ontology(
    alive_frac: float,
    dynamic_frac: float,
    *,
    alive_threshold: float = 0.5,
    dynamic_threshold: float = 0.5,
) -> str:
    """Gate: verify INV-YV1 — ΔV > 0 ∧ dΔV/dt ≠ 0.

    Does not raise — returns diagnosis string. Callers decide severity.
    A system at dead equilibrium or static capacitor is not intelligent;
    it is not an error, it is an ontological state.

    Returns:
        "living_gradient", "static_capacitor", "dead_equilibrium",
        or "transient".
    """
    if alive_frac <= alive_threshold:
        return "dead_equilibrium"
    if dynamic_frac <= dynamic_threshold:
        return "static_capacitor"
    if alive_frac > 0.9 and dynamic_frac > 0.9:
        return "living_gradient"
    return "transient"


# ---------------------------------------------------------------------------
# Contract registry
# ---------------------------------------------------------------------------
INVARIANTS = {
    "YV1": {
        "name": "GRADIENT_ONTOLOGY",
        "axiom": "INV-YV1",
        "rule": "ΔV > 0 ∧ dΔV/dt ≠ 0 — system must maintain a living gradient",
        "reason": (
            "existence = sustained non-equilibrium; "
            "static gradient = capacitor; "
            "zero gradient = noise"
        ),
        "enforcement": "enforce_gradient_ontology() returns diagnosis",
    },
    "I": {
        "name": "GAMMA_DERIVED_ONLY",
        "axiom": "AXIOM_0",
        "rule": "gamma is computed via observe()->theilslopes(), never assigned",
        "reason": "gamma is a signature of the regime, not a metric",
        "enforcement": "enforce_gamma_derived() raises InvariantViolation",
    },
    "II": {
        "name": "STATE_NOT_PROOF",
        "axiom": "AXIOM_0",
        "rule": "state source != proof source; proof requires independent substrate",
        "reason": "a system is not an independent witness of itself",
        "enforcement": "enforce_state_not_proof() raises InvariantViolation",
    },
    "III": {
        "name": "BOUNDED_MODULATION",
        "axiom": "AXIOM_0",
        "rule": "|modulation| <= 0.05 always",
        "reason": "unbounded modulation = regime collapse",
        "enforcement": "enforce_bounded_modulation() clamps value",
    },
    "IV": {
        "name": "SSI_DOMAIN_EXTERNAL_ONLY",
        "axiom": "AXIOM_0",
        "rule": "SSI.apply(domain=EXTERNAL) valid; SSI.apply(domain=INTERNAL) forbidden",
        "reason": "internal self-obfuscation corrupts gamma via contaminated observe()",
        "enforcement": "ssi_enforce_domain() raises InvariantViolation",
    },
}

# INV-1: gamma DERIVED ONLY. Values from canonical ledger.
from core.gamma_registry import GammaRegistry as _GR

SUBSTRATE_GAMMA = {
    name: _GR.get(eid, "gamma")
    for name, eid in [
        ("zebrafish", "zebrafish_wt"),
        ("gray_scott", "gray_scott"),
        ("kuramoto_market", "kuramoto"),
        ("bn_syn", "bnsyn"),
        ("eeg_physionet", "eeg_physionet"),
        ("hrv_physionet", "hrv_physionet"),
        ("eeg_resting", "eeg_resting"),
        ("serotonergic_kuramoto", "serotonergic_kuramoto"),
        ("hrv_fantasia", "hrv_fantasia"),
    ]
    if _GR.get(eid, "gamma") is not None
}


def verify_all() -> None:
    """Self-test all contracts. Called by CI INV-3 gate."""
    # INV-IV: SSI domain enforcement
    try:
        ssi_enforce_domain(SSIDomain.INTERNAL)
        raise AssertionError("INV-IV: should have raised")
    except InvariantViolation:
        pass
    ssi_apply(signal="test", domain=SSIDomain.EXTERNAL)

    # INV-I: gamma derived enforcement
    enforce_gamma_derived("computed")
    try:
        enforce_gamma_derived("assigned")
        raise AssertionError("INV-I: should have raised")
    except InvariantViolation:
        pass

    # INV-II: state != proof
    enforce_state_not_proof("nfi", "bn_syn")
    try:
        enforce_state_not_proof("nfi", "nfi")
        raise AssertionError("INV-II: should have raised")
    except InvariantViolation:
        pass

    # INV-III: bounded modulation
    assert enforce_bounded_modulation(0.1) == 0.05
    assert enforce_bounded_modulation(-0.1) == -0.05

    # Gamma registry loaded
    assert len(SUBSTRATE_GAMMA) >= 6
