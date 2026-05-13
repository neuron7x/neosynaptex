from __future__ import annotations

from dataclasses import dataclass

from core.eai.engine import EAIEngine
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimStatus,
    ClaimType,
    ReproducibilityManifest,
)


@dataclass
class LeverageReport:
    baseline_status: ClaimStatus
    sensitivities: dict[str, float]
    top_leverage_parameter: str


def _score(status: ClaimStatus) -> float:
    return {
        ClaimStatus.KILLED: 0.0,
        ClaimStatus.QUARANTINED: 0.5,
        ClaimStatus.EVIDENCE: 1.0,
    }[status]


def estimate_gate_leverage() -> LeverageReport:
    claim = ClaimCard("CLM-LEV-1", "bounded local claim", ClaimType.FACTUAL)
    boundary = BoundaryCard("BND-LEV-1", ["local"], ["global"], ["local"], ["global"])
    repro = ReproducibilityManifest(["pytest"], "local", "a" * 64)

    def run(
        *, contradictions: list[str], retention_hash: str, revalidation_passed: bool
    ) -> ClaimStatus:
        engine = EAIEngine()
        try:
            out = engine.run_candidate(
                claim=claim,
                boundary=boundary,
                contradiction_markers=contradictions,
                reproducibility=repro,
                retention_hash=retention_hash,
                revalidation_passed=revalidation_passed,
                integration_patch={"guardrail_update": {"id": "GR-LEV-1"}},
                next_intent_delta={"delta": 1},
            )
            return out.status
        except ValueError:
            return ClaimStatus.QUARANTINED

    baseline = run(contradictions=[], retention_hash="a" * 64, revalidation_passed=True)
    base_score = _score(baseline)

    variants = {
        "contradiction_markers": run(
            contradictions=["bounded"], retention_hash="a" * 64, revalidation_passed=True
        ),
        "retention_hash_validity": run(
            contradictions=[], retention_hash="bad", revalidation_passed=True
        ),
        "revalidation_passed": run(
            contradictions=[], retention_hash="a" * 64, revalidation_passed=False
        ),
    }
    sensitivities = {k: abs(_score(v) - base_score) for k, v in variants.items()}
    top = max(sensitivities, key=lambda k: sensitivities[k])
    return LeverageReport(
        baseline_status=baseline, sensitivities=sensitivities, top_leverage_parameter=top
    )
