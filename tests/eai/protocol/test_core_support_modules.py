from core.boundary_lock import within_boundary
from core.claim_classifier import classify_claim_type
from core.eai.intelligence_cycle import BoundaryCard, ClaimType
from core.evidence_compressor import compress_evidence_text
from core.null_model_battery import reject_obvious_overclaim


def test_boundary_lock_enforces_valid_context() -> None:
    boundary = BoundaryCard("BND-LOCK-1", ["local"], ["global"], ["local"], ["global"])
    assert within_boundary(boundary, "local")
    assert not within_boundary(boundary, "global")
    assert not within_boundary(None, "local")


def test_claim_classifier_defaults_and_keyword_mapping() -> None:
    assert classify_claim_type("This is a security critical issue") is ClaimType.SECURITY
    assert classify_claim_type("A plain statement") is ClaimType.FACTUAL


def test_evidence_compressor_is_deterministic_for_whitespace_variants() -> None:
    a = compress_evidence_text("claim   with  spaces")
    b = compress_evidence_text("claim with spaces")
    assert a == b and len(a) == 64


def test_null_model_battery_rejects_overclaim_patterns() -> None:
    assert reject_obvious_overclaim("This proves consciousness in all systems")
    assert not reject_obvious_overclaim("validated locally for this test only")
