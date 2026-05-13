from __future__ import annotations

from dataclasses import dataclass, field

from core.eai.engine import EngineOutcome
from core.eai.intelligence_cycle import ClaimStatus


@dataclass
class LoopArchitecture:
    revalidation_bias: float = 0.0
    contradiction_sensitivity: float = 0.0


@dataclass
class LoopIntegrator:
    """Action -> feedback -> compression -> architecture-update loop."""

    architecture: LoopArchitecture = field(default_factory=LoopArchitecture)
    compressed_rules: list[str] = field(default_factory=list)

    def apply_feedback(self, outcome: EngineOutcome) -> None:
        if outcome.status is ClaimStatus.KILLED:
            self.architecture.contradiction_sensitivity += 0.1
            self._compress("killed_requires_stricter_falsification")
            return

        if outcome.status is ClaimStatus.QUARANTINED:
            self.architecture.revalidation_bias += 0.1
            self._compress("quarantine_requires_stronger_revalidation")
            return

        self.architecture.revalidation_bias = max(0.0, self.architecture.revalidation_bias - 0.05)
        self.architecture.contradiction_sensitivity = max(
            0.0, self.architecture.contradiction_sensitivity - 0.05
        )
        self._compress("evidence_allows_gradual_relaxation")

    def _compress(self, rule: str) -> None:
        if rule not in self.compressed_rules:
            self.compressed_rules.append(rule)
