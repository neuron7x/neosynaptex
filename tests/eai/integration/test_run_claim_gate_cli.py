from tools.eai.run_claim_gate import run_claim_gate


def test_run_claim_gate_reports_quarantine_without_revalidation() -> None:
    report = run_claim_gate(
        claim_text="bounded local claim",
        context="local",
        retention_hash="a" * 64,
        revalidation_passed=False,
    )
    assert report["status"] == "QUARANTINED"
    assert report["timestamp_utc"].endswith("+00:00")
    assert report["artifact_owner"] == "eai-research-track"
    assert report["telemetry"]["elapsed_ms"] >= 0.0


def test_run_claim_gate_reports_evidence_with_revalidation() -> None:
    report = run_claim_gate(
        claim_text="bounded local claim",
        context="local",
        retention_hash="a" * 64,
        revalidation_passed=True,
    )
    assert report["status"] == "EVIDENCE"


def test_run_claim_gate_kill_switch_overrides_decision() -> None:
    report = run_claim_gate(
        claim_text="bounded local claim",
        context="local",
        retention_hash="a" * 64,
        revalidation_passed=True,
        kill_switch=True,
    )
    assert report["status"] == "KILLED"


def test_run_claim_gate_emits_decision_trace_fields() -> None:
    report = run_claim_gate(
        claim_text="bounded local claim",
        context="local",
        retention_hash="a" * 64,
        revalidation_passed=False,
    )
    assert report["decision_reason"]
    assert report["failed_stage"] == "iev_gate"
    assert "falsification" in report["telemetry"]["path"]
