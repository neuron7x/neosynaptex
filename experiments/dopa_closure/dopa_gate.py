"""DOPA-CLOSURE verification-prediction-error gate (pure, no I/O).

The single falsifiable mechanism from the pre-registration: turn a *cheap probe*
into a verification-prediction-error ``vRPE`` and route a fixed verification
budget on its magnitude. If this carries no information beyond the raw
confidence margin, the gate is decorative (RFC sec. 13.3 / H0.6).

Yaroslav Vasylenko / neuron7xLab / 2026
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class GateMode(str, Enum):
    """Routing decision emitted by the DOPA gate."""

    BYPASS = "BYPASS"
    VERIFY = "VERIFY"


@dataclass(frozen=True)
class GateDecision:
    """Auditable record of one gate evaluation."""

    margin: float
    confidence: float
    q_expected: float
    q_observed: float
    vrpe: float
    mode: GateMode


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def expected_quality(margin: float, k_conf: float) -> float:
    """Expected verdict stability from the confidence margin alone.

    Maps ``|margin|`` through a sigmoid into (0.5, 1). This is the *only*
    information ``uncertainty_only`` (the no-vRPE ablation) is allowed to use.
    """

    return _sigmoid(k_conf * abs(margin))


def evaluate_gate(
    *,
    margin: float,
    cheap_verdict: bool,
    probe_verdict: bool,
    k_conf: float,
    tau: float,
    invert: bool = False,
) -> GateDecision:
    """Compute vRPE from one cheap probe and decide VERIFY vs BYPASS.

    ``invert=True`` is the negative control: it routes the budget at the
    *unsurprising* scenarios instead, and must collapse to ``random_gate``.
    """

    confidence = abs(margin)
    q_expected = expected_quality(margin, k_conf)
    q_observed = 1.0 if probe_verdict == cheap_verdict else 0.0
    vrpe = q_observed - q_expected

    surprising = abs(vrpe) >= tau
    do_verify = (not surprising) if invert else surprising
    mode = GateMode.VERIFY if do_verify else GateMode.BYPASS

    return GateDecision(
        margin=margin,
        confidence=confidence,
        q_expected=q_expected,
        q_observed=q_observed,
        vrpe=vrpe,
        mode=mode,
    )


def majority_verdict(votes: list[bool]) -> bool:
    """Majority over boolean hallucination verdicts; ties → True (conservative)."""

    if not votes:
        raise ValueError("majority_verdict requires at least one vote")
    positive = sum(1 for v in votes if v)
    return positive * 2 >= len(votes)
