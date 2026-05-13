from core.integration_memory import IntegrationMemory


def test_integration_memory_snapshot_and_rollback() -> None:
    mem = IntegrationMemory()
    assert mem.apply_patch(claim_id="CLM-1", status="EVIDENCE", patch={"v": 1})
    mem.snapshot("stable")
    assert mem.apply_patch(claim_id="CLM-1", status="EVIDENCE", patch={"v": 2})
    assert mem.get("CLM-1") == {"v": 2}
    assert mem.rollback("stable")
    assert mem.get("CLM-1") == {"v": 1}


def test_integration_memory_rollback_missing_tag_returns_false() -> None:
    mem = IntegrationMemory()
    assert not mem.rollback("missing")
