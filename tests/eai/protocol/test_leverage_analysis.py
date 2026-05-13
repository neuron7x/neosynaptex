from core.eai.intelligence_cycle import ClaimStatus
from core.eai.leverage import estimate_gate_leverage


def test_estimate_gate_leverage_returns_ranked_sensitivities() -> None:
    report = estimate_gate_leverage()
    assert report.baseline_status is ClaimStatus.EVIDENCE
    assert set(report.sensitivities) == {
        "contradiction_markers",
        "retention_hash_validity",
        "revalidation_passed",
    }
    assert report.sensitivities[report.top_leverage_parameter] >= 0.5
