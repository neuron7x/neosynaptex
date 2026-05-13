from core.eai.engine import EAIEngine
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimStatus,
    ClaimType,
    ReproducibilityManifest,
)


def _inputs() -> tuple[ClaimCard, BoundaryCard, ReproducibilityManifest]:
    claim = ClaimCard("CLM-ENG-1", "local bounded claim", ClaimType.FACTUAL)
    boundary = BoundaryCard("BND-ENG-1", ["local"], ["global"], ["local"], ["global"])
    repro = ReproducibilityManifest(["python -m pytest"], "local", "a" * 64)
    return claim, boundary, repro


def test_engine_promotes_evidence_and_updates_memory() -> None:
    claim, boundary, repro = _inputs()
    engine = EAIEngine()
    out = engine.run_candidate(
        claim=claim,
        boundary=boundary,
        contradiction_markers=[],
        reproducibility=repro,
        retention_hash="a" * 64,
        revalidation_passed=True,
        integration_patch={"guardrail_update": {"id": "GR-1"}},
        next_intent_delta={"delta": 1},
    )
    assert out.status is ClaimStatus.EVIDENCE
    assert out.decision_reason == "promotion_allowed"
    assert out.failed_stage is None
    assert out.telemetry.elapsed_ms >= 0.0
    assert out.telemetry.path[-1] == "artifact_ledger"
    assert engine.memory.get(claim.claim_id) == {"guardrail_update": {"id": "GR-1"}}


def test_engine_quarantines_when_revalidation_fails() -> None:
    claim, boundary, repro = _inputs()
    engine = EAIEngine()
    out = engine.run_candidate(
        claim=claim,
        boundary=boundary,
        contradiction_markers=[],
        reproducibility=repro,
        retention_hash="a" * 64,
        revalidation_passed=False,
        integration_patch={"guardrail_update": {"id": "GR-1"}},
        next_intent_delta={"delta": 1},
    )
    assert out.status is ClaimStatus.QUARANTINED
    assert out.failed_stage == "iev_gate"
    assert "integration_memory" not in out.telemetry.path
    assert engine.memory.get(claim.claim_id) is None
