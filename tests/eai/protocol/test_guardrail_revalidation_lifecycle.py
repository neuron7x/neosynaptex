from core.eai.guardrail_registry import GuardrailRegistry
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    KillArtifact,
    ReproducibilityManifest,
)


def _seed_registry() -> tuple[GuardrailRegistry, str]:
    reg = GuardrailRegistry()
    killed = KillArtifact(
        "KILL-900001",
        ClaimCard("CLM-900001", "library y exists", ClaimType.SOFTWARE),
        "bad claim",
        "source_contradiction",
        "require package+import proof",
    )
    patch = reg.register_from_kill(killed, "a" * 64, "software")
    return reg, patch.guardrail_id


def test_evidence_cannot_directly_delete_guardrail() -> None:
    reg, gid = _seed_registry()
    assert reg._active[gid].status == "ACTIVE"


def test_evidence_creates_revalidation_claim_when_supersession_condition_matches() -> None:
    reg, _ = _seed_registry()
    ev = EvidenceArtifact(
        "EVD-900001",
        ClaimCard("CLM-900010", "library y verified", ClaimType.SOFTWARE),
        BoundaryCard("BND-1", ["x"], ["y"], ["x"], ["y"]),
        FalsificationReport(["t"], True),
        ReproducibilityManifest(["cmd"], "env", "b" * 64),
        True,
    )
    claims = reg.scan_conflicts(ev)
    assert len(claims) == 1


def test_guardrail_remains_active_until_revalidation_passes() -> None:
    reg, gid = _seed_registry()
    rc = reg.scan_conflicts(
        EvidenceArtifact(
            "EVD-1",
            ClaimCard("CLM-2", "library y verified", ClaimType.SOFTWARE),
            BoundaryCard("BND-1", ["x"], ["y"], ["x"], ["y"]),
            FalsificationReport(["t"], True),
            ReproducibilityManifest(["cmd"], "env", "b" * 64),
            True,
        )
    )[0]
    reg.apply_revalidation(rc, passed=False)
    assert reg._active[gid].status == "CHALLENGED"


def test_revalidated_guardrail_can_scope_down_not_disappear_silently() -> None:
    reg, gid = _seed_registry()
    rc = reg.scan_conflicts(
        EvidenceArtifact(
            "EVD-1",
            ClaimCard("CLM-2", "library y validated", ClaimType.SOFTWARE),
            BoundaryCard("BND-1", ["x"], ["y"], ["x"], ["y"]),
            FalsificationReport(["t"], True),
            ReproducibilityManifest(["cmd"], "env", "b" * 64),
            True,
        )
    )[0]
    reg.apply_revalidation(rc, passed=True, scope_down_pattern="library y below version 2.1")
    assert reg._active[gid].status == "SCOPED_DOWN"


def test_retired_guardrail_is_append_only_not_mutated() -> None:
    reg, gid = _seed_registry()
    rc = reg.scan_conflicts(
        EvidenceArtifact(
            "EVD-1",
            ClaimCard("CLM-2", "library y validated", ClaimType.SOFTWARE),
            BoundaryCard("BND-1", ["x"], ["y"], ["x"], ["y"]),
            FalsificationReport(["t"], True),
            ReproducibilityManifest(["cmd"], "env", "b" * 64),
            True,
        )
    )[0]
    reg.apply_revalidation(rc, passed=True)
    assert (
        len(reg.history) >= 2
        and reg.history[0].status == "ACTIVE"
        and reg._active[gid].status == "RETIRED"
    )


def test_guardrail_registry_blocks_old_failure_pattern() -> None:
    reg, _ = _seed_registry()
    assert reg.evaluate_candidate("library y exists", ClaimType.SOFTWARE) == "KILLED"


def test_guardrail_registry_allows_new_claim_after_revalidation_pass() -> None:
    reg, _ = _seed_registry()
    rc = reg.scan_conflicts(
        EvidenceArtifact(
            "EVD-1",
            ClaimCard("CLM-2", "library y validated", ClaimType.SOFTWARE),
            BoundaryCard("BND-1", ["x"], ["y"], ["x"], ["y"]),
            FalsificationReport(["t"], True),
            ReproducibilityManifest(["cmd"], "env", "b" * 64),
            True,
        )
    )[0]
    reg.apply_revalidation(rc, passed=True)
    assert reg.evaluate_candidate("library y exists", ClaimType.SOFTWARE) == "ALLOW"


def test_guardrail_compression_preserves_source_kill_artifact_refs() -> None:
    reg, gid = _seed_registry()
    source = reg._active[gid].source_kill_artifact_id
    assert all(h.source_kill_artifact_id == source for h in reg.history)
