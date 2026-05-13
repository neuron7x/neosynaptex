from core.eai.engine import EAIEngine, EngineOutcome
from core.eai.integrator import LoopIntegrator
from core.eai.intelligence_cycle import BoundaryCard, ClaimCard, ClaimType, ReproducibilityManifest


def _run(*, claim_text: str, revalidation_passed: bool) -> EngineOutcome:
    engine = EAIEngine()
    return engine.run_candidate(
        claim=ClaimCard("CLM-LOOP-1", claim_text, ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-LOOP-1", ["local"], ["global"], ["local"], ["global"]),
        contradiction_markers=["bounded"] if "bounded" in claim_text else [],
        reproducibility=ReproducibilityManifest(["pytest"], "local", "a" * 64),
        retention_hash="a" * 64,
        revalidation_passed=revalidation_passed,
        integration_patch={"guardrail_update": {"id": "GR-LOOP"}},
        next_intent_delta={"delta": 1},
    )


def test_loop_integrator_strengthens_on_quarantine_and_kill() -> None:
    integ = LoopIntegrator()
    q = _run(claim_text="local claim", revalidation_passed=False)
    integ.apply_feedback(q)
    k = _run(claim_text="bounded impossible", revalidation_passed=True)
    integ.apply_feedback(k)

    assert integ.architecture.revalidation_bias > 0
    assert integ.architecture.contradiction_sensitivity > 0
    assert "quarantine_requires_stronger_revalidation" in integ.compressed_rules
    assert "killed_requires_stricter_falsification" in integ.compressed_rules
