"""Regression tests for the two engine fan-out bugs flagged by Codex review on PR #192.

1. When ``decide_intent_update`` returns ``KILLED`` (because
   ``EvidenceArtifact.can_be_promoted()`` returns ``False`` — e.g.
   boundary unbounded or reproducibility hash invalid), the engine
   must synthesise a ``KillArtifact``, NOT a ``QuarantinedClaim``.
   Downstream policy (ICU high-quality-kill, guardrail derivation)
   depends on the kill metadata being present.
2. A malformed ``retention_hash`` must NEVER turn a policy decision
   into a ``ValueError`` from the ledger. The engine substitutes a
   deterministic fallback so the QUARANTINED / KILLED record is
   still committed, preserving audit semantics.
"""

from __future__ import annotations

import re

from core.eai.engine import EAIEngine, _safe_retention_hash
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimStatus,
    ClaimType,
    KillArtifact,
    QuarantinedClaim,
    ReproducibilityManifest,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _claim() -> ClaimCard:
    return ClaimCard("CLM-FAN-1", "bounded local claim", ClaimType.FACTUAL)


def _boundary() -> BoundaryCard:
    return BoundaryCard("BND-FAN-1", ["local"], ["global"], ["local"], ["global"])


def _repro_invalid_hash() -> ReproducibilityManifest:
    # artifact_hash is NOT a SHA-256 hex digest -> can_be_promoted() returns False.
    return ReproducibilityManifest(["pytest"], "local", "not-a-hex-digest")


def _repro_valid() -> ReproducibilityManifest:
    return ReproducibilityManifest(["pytest"], "local", "a" * 64)


def test_iev_gate_killed_synthesises_kill_artifact_not_quarantined() -> None:
    engine = EAIEngine()
    out = engine.run_candidate(
        claim=_claim(),
        boundary=_boundary(),
        contradiction_markers=[],
        reproducibility=_repro_invalid_hash(),
        retention_hash="a" * 64,
        revalidation_passed=True,
        integration_patch={"guardrail_update": {"id": "GR-FAN-1"}},
        next_intent_delta={"delta": 1},
    )
    assert out.status is ClaimStatus.KILLED
    assert isinstance(out.icu.artifact, KillArtifact)
    assert out.icu.artifact.kill_reason == "iev_gate_promotion_denied"
    assert out.icu.artifact.future_guardrail.startswith("block_repromotion")
    assert out.icu.artifact.is_high_quality_kill()
    assert out.ledger_entry.artifact_id.startswith("KILL-")
    assert out.decision_reason == "iev_gate_promotion_denied"


def test_quarantine_path_with_invalid_retention_hash_does_not_raise() -> None:
    engine = EAIEngine()
    out = engine.run_candidate(
        claim=_claim(),
        boundary=_boundary(),
        contradiction_markers=[],
        reproducibility=_repro_valid(),
        retention_hash="NOT-A-VALID-HEX",  # malformed -> IEV returns QUARANTINED
        revalidation_passed=True,
        integration_patch=None,
        next_intent_delta=None,
    )
    assert out.status is ClaimStatus.QUARANTINED
    assert isinstance(out.icu.artifact, QuarantinedClaim)
    # The engine must have substituted a valid SHA-256 hex digest for the ledger.
    assert _SHA256_HEX.fullmatch(out.ledger_entry.retention_hash)
    assert out.decision_reason == "gate_quarantine"


def test_kill_path_with_invalid_retention_hash_does_not_raise() -> None:
    engine = EAIEngine()
    out = engine.run_candidate(
        claim=_claim(),
        boundary=_boundary(),
        contradiction_markers=["bounded"],  # forces falsification fail -> KILLED
        reproducibility=_repro_valid(),
        retention_hash="garbage",
        revalidation_passed=True,
        integration_patch=None,
        next_intent_delta=None,
    )
    assert out.status is ClaimStatus.KILLED
    assert isinstance(out.icu.artifact, KillArtifact)
    assert _SHA256_HEX.fullmatch(out.ledger_entry.retention_hash)


def test_safe_retention_hash_is_deterministic_and_audit_stable() -> None:
    a = _safe_retention_hash("garbage", status="KILLED", claim_id="CLM-X", claim_text="some text")
    b = _safe_retention_hash(
        "also-garbage", status="KILLED", claim_id="CLM-X", claim_text="some text"
    )
    # Different malformed inputs collapse to the same deterministic fallback
    # (status:claim_id:claim_text), preserving audit reproducibility.
    assert a == b
    assert _SHA256_HEX.fullmatch(a)


def test_safe_retention_hash_passes_through_valid_input() -> None:
    valid = "f" * 64
    out = _safe_retention_hash(valid, status="EVIDENCE", claim_id="CLM-Y", claim_text="text")
    assert out == valid
