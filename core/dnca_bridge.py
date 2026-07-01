"""DNCA↔Neosynaptex Bridge — formal coupling between agent layer and root engine.

Syncs gamma, regime/phase, and neuromodulation between DNCA probes
and the neosynaptex observation loop. All modulation bounded |Δ| ≤ 0.05.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "DivergenceReport",
    "DncaBridge",
]

logger = logging.getLogger(__name__)

_MOD_BOUND = 0.05


@dataclass(frozen=True)
class DivergenceReport:
    gamma_delta: float
    phase_match: bool
    modulation_delta: dict[str, float]
    warnings: tuple[str, ...]


class DncaBridge:
    """Bridge between DNCA orchestrator and Neosynaptex engine.

    Syncs gamma estimates, regime classifications, and neuromodulation
    signals between the two systems.
    """

    def __init__(self, dnca: Any = None, engine: Any = None) -> None:
        self._dnca = dnca
        self._engine = engine
        self._sync_history: list[DivergenceReport] = []

    def _fail_closed(self) -> bool:
        return os.getenv("NFI_FAIL_CLOSED") == "1"

    def sync_gamma(self) -> dict[str, float]:
        """Read gamma from DNCA probes, compare with neosynaptex gamma.

        Returns dict with dnca_gamma, neosynaptex_gamma, delta.
        """
        dnca_gamma = self._get_dnca_gamma()
        neo_gamma = self._get_neosynaptex_gamma()

        both_finite = np.isfinite(dnca_gamma) and np.isfinite(neo_gamma)
        delta = dnca_gamma - neo_gamma if both_finite else float("nan")

        if np.isfinite(delta) and abs(delta) > 0.2:
            logger.warning(
                "Gamma divergence: DNCA=%.4f Neo=%.4f delta=%.4f",
                dnca_gamma,
                neo_gamma,
                delta,
            )

        return {
            "dnca_gamma": dnca_gamma,
            "neosynaptex_gamma": neo_gamma,
            "delta": delta,
        }

    def sync_regime(self) -> dict[str, str]:
        """Map DNCA regime to neosynaptex phase."""
        dnca_regime = self._get_dnca_regime()
        neo_phase = self._get_neosynaptex_phase()

        # DNCA regime → neosynaptex phase mapping
        regime_to_phase = {
            "critical": "METASTABLE",
            "subcritical": "COLLAPSING",
            "supercritical": "DIVERGING",
            "metastable": "METASTABLE",
            "chaotic": "DEGENERATE",
        }
        mapped = regime_to_phase.get(dnca_regime.lower(), "INITIALIZING")
        match = mapped == neo_phase

        return {
            "dnca_regime": dnca_regime,
            "neosynaptex_phase": neo_phase,
            "mapped_phase": mapped,
            "phase_match": "true" if match else "false",
        }

    def sync_neuromodulation(self) -> dict[str, float]:
        """Convert DNCA neuromod levels to bounded neosynaptex modulation.

        INV: |Δmod| ≤ 0.05. Even if DNCA wants more — clamp.
        """
        dnca_mods = self._get_dnca_neuromod()
        bounded: dict[str, float] = {}

        for key, value in dnca_mods.items():
            clamped = float(np.clip(value, -_MOD_BOUND, _MOD_BOUND))
            bounded[key] = round(clamped, 6)

        return bounded

    def get_divergence_report(self) -> DivergenceReport:
        """Full report of where DNCA and NeoSynaptex diverge."""
        gamma_sync = self.sync_gamma()
        regime_sync = self.sync_regime()
        mod_sync = self.sync_neuromodulation()

        warnings: list[str] = []
        delta = gamma_sync["delta"]
        if np.isfinite(delta) and abs(delta) > 0.2:
            warnings.append(f"gamma divergence: {delta:.4f}")
        phase_match = regime_sync["phase_match"] == "true"
        if not phase_match:
            warnings.append(
                f"phase mismatch: DNCA={regime_sync['dnca_regime']} "
                f"Neo={regime_sync['neosynaptex_phase']}"
            )

        report = DivergenceReport(
            gamma_delta=delta,
            phase_match=phase_match,
            modulation_delta=mod_sync,
            warnings=tuple(warnings),
        )
        self._sync_history.append(report)
        return report

    @property
    def history(self) -> list[DivergenceReport]:
        return list(self._sync_history)

    # --- Internal getters (safe with None engine/dnca) ---

    def _get_dnca_gamma(self) -> float:
        if self._dnca is None:
            return float("nan")
        try:
            if hasattr(self._dnca, "get_gamma"):
                return float(self._dnca.get_gamma())
            if hasattr(self._dnca, "gamma"):
                return float(self._dnca.gamma)
        except Exception as exc:  # nosec B110  # graceful degradation: DNCA subsystem optional
            if self._fail_closed():
                raise RuntimeError("DNCA gamma query failed under fail-closed mode") from exc
        return float("nan")

    def _get_neosynaptex_gamma(self) -> float:
        if self._engine is None:
            return float("nan")
        try:
            history = self._engine.history()
            if history:
                return float(history[-1].gamma_mean)
        except Exception as exc:  # nosec B110  # graceful degradation: engine history may be empty
            if self._fail_closed():
                raise RuntimeError("Neosynaptex gamma query failed under fail-closed mode") from exc
        return float("nan")

    def _get_dnca_regime(self) -> str:
        if self._dnca is None:
            return "unknown"
        try:
            if hasattr(self._dnca, "get_regime"):
                return str(self._dnca.get_regime())
            if hasattr(self._dnca, "regime"):
                return str(self._dnca.regime)
        except Exception as exc:  # nosec B110  # graceful degradation: DNCA regime query optional
            if self._fail_closed():
                raise RuntimeError("DNCA regime query failed under fail-closed mode") from exc
        return "unknown"

    def _get_neosynaptex_phase(self) -> str:
        if self._engine is None:
            return "INITIALIZING"
        try:
            history = self._engine.history()
            if history:
                return str(history[-1].phase)
        except Exception as exc:  # nosec B110  # graceful degradation: engine phase query optional
            if self._fail_closed():
                raise RuntimeError("Neosynaptex phase query failed under fail-closed mode") from exc
        return "INITIALIZING"

    def _get_dnca_neuromod(self) -> dict[str, float]:
        if self._dnca is None:
            return {}
        try:
            if hasattr(self._dnca, "get_neuromodulation"):
                return dict(self._dnca.get_neuromodulation())
            if hasattr(self._dnca, "neuromod_levels"):
                return dict(self._dnca.neuromod_levels)
        except Exception as exc:  # nosec B110  # graceful degradation: DNCA neuromod optional
            if self._fail_closed():
                raise RuntimeError("DNCA neuromod query failed under fail-closed mode") from exc
        return {}
