from itertools import product

from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)
from core.iev_gate import decide_intent_update


def _artifact(hash_value: str, passed: bool = True) -> EvidenceArtifact:
    return EvidenceArtifact(
        artifact_id="EVD-PROP-1",
        claim=ClaimCard("CLM-PROP-1", "bounded claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-PROP-1", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["falsify"], passed),
        reproducibility=ReproducibilityManifest(["cmd"], "env", hash_value),
        integration_permission=True,
    )


def test_non_sha256_hash_never_allows_evidence_status() -> None:
    invalid_hashes = ["", "abc", "g" * 64, "A" * 64, "1234" * 8]
    for random_hash in invalid_hashes:
        status = decide_intent_update(
            _artifact(random_hash), retention_hash="a" * 64, revalidation_passed=True
        )
        assert status != "EVIDENCE"


def test_gate_is_fail_closed_on_missing_retention_or_revalidation() -> None:
    for has_retention, has_revalidation in product([False, True], [False, True]):
        status = decide_intent_update(
            _artifact("a" * 64),
            retention_hash=("a" * 64) if has_retention else None,
            revalidation_passed=has_revalidation,
        )
        if has_retention and has_revalidation:
            assert status == "EVIDENCE"
        else:
            assert status == "QUARANTINED"
