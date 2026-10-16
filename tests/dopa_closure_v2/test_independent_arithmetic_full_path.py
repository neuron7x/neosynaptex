"""Real allocator -> precommitted exact claim -> independent oracle integration."""
from __future__ import annotations

import json
from pathlib import Path

from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_independent_verifier import (
    ArithmeticClaim, arithmetic_commitment, verify_scheduled_arithmetic,
)
from core.eai.dopa_result import Err, Ok
from core.eai.dopa_types import ClaimSignal

CONFIG = "configs/dopa_closure_v2/allocator.yaml"
ROUTING_ONLY = ConstructContext(True, True, False, False, True, True)


def _score(claim_id: str) -> ClaimSignal:
    return ClaimSignal(claim_id, 0.6, 0.7, 0.6, 0.1, 0.8, 0.55)


def test_real_route_precommit_verifier_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", "arith-001")
    case = ArithmeticClaim("A-01", "multiply", 3, 4, 12)
    result = run_allocator_full_path(
        CONFIG, [_score(case.claim_id)], tmp_path, ROUTING_ONLY,
        claim_commitments={case.claim_id: arithmetic_commitment(case)},
    )
    assert isinstance(result, Ok), result
    routing = result.value
    assert routing["final_verdict"] == "INADMISSIBLE"
    route = routing["routes"][0]
    assert route["claim_payload_sha256"] == arithmetic_commitment(case)
    assert route["route_mode"] == "verify"
    run = tmp_path / "runs" / "arith-001"
    receipt = verify_scheduled_arithmetic(run, case)
    assert receipt["verdict"] == "VERIFIED"
    assert receipt["computed"] == 12
    assert receipt["route_sha256"]
    assert json.loads((run / "final_verdict.json").read_text())["final_verdict"] == (
        "INADMISSIBLE"
    )
    assert not (run / "claims" / case.claim_id / "closure_artifact.json").exists()


def test_precommit_wrong_content_rejected_before_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", "arith-002")
    case = ArithmeticClaim("A-02", "add", 12, 4, 16)
    result = run_allocator_full_path(
        CONFIG, [_score(case.claim_id)], tmp_path, ROUTING_ONLY,
        claim_commitments={case.claim_id: arithmetic_commitment(case)},
    )
    assert isinstance(result, Ok)
    from pytest import raises

    with raises(ValueError, match="claim_payload_commitment_mismatch"):
        verify_scheduled_arithmetic(
            tmp_path / "runs" / "arith-002",
            ArithmeticClaim("A-02", "add", 12, 4, 99),
        )


def test_missing_commitment_blocks_receipts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", "arith-003")
    case = ArithmeticClaim("A-03", "multiply", 3, 4, 12)
    result = run_allocator_full_path(CONFIG, [_score(case.claim_id)], tmp_path, ROUTING_ONLY)
    assert isinstance(result, Ok)
    from pytest import raises

    with raises(ValueError, match="claim_payload_commitment_mismatch"):
        verify_scheduled_arithmetic(tmp_path / "runs" / "arith-003", case)


def test_bad_commitments_rejected_before_file_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", "arith-004")
    case = ArithmeticClaim("A-04", "add", 3, 4, 7)
    for commitments in ({}, {case.claim_id: "bad"}, {"other": "a"*64}):
        result = run_allocator_full_path(
            CONFIG, [_score(case.claim_id)], tmp_path, ROUTING_ONLY,
            claim_commitments=commitments,
        )
        assert isinstance(result, Err)
        assert not (tmp_path / "runs").exists()


def test_full_path_authenticated_run_receipt(tmp_path: Path, monkeypatch) -> None:
    """Actual allocator output is bound by a separately provisioned key."""
    from core.eai.dopa_run_attestation import seal_arithmetic_run

    monkeypatch.setenv("DOPA_RUN_ID", "arith-auth-001")
    claim = ArithmeticClaim("auth-1", "multiply", 12, 11, 132)
    result = run_allocator_full_path(
        CONFIG, [_score(claim.claim_id)], tmp_path, ROUTING_ONLY,
        claim_commitments={claim.claim_id: arithmetic_commitment(claim)},
    )
    assert isinstance(result, Ok), result
    root = tmp_path / "runs" / "arith-auth-001"
    key = b"test-vector-only-not-production!" + b"1234567890"
    seal_arithmetic_run(root, claim.claim_id, key)
    receipt = verify_scheduled_arithmetic(root, claim, attestation_key=key)
    assert receipt["verdict"] == "VERIFIED"
    assert receipt["archive_authentication"] == "HMAC_AUTHENTICATED"
    assert len(receipt["attestation_sha256"]) == 64
    assert result.value["final_verdict"] == "INADMISSIBLE"


def test_full_path_wrong_attestation_key_fails_without_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    from core.eai.dopa_run_attestation import seal_arithmetic_run
    import pytest

    monkeypatch.setenv("DOPA_RUN_ID", "arith-auth-002")
    claim = ArithmeticClaim("auth-2", "add", 12, 11, 23)
    result = run_allocator_full_path(
        CONFIG, [_score(claim.claim_id)], tmp_path, ROUTING_ONLY,
        claim_commitments={claim.claim_id: arithmetic_commitment(claim)},
    )
    assert isinstance(result, Ok), result
    root = tmp_path / "runs" / "arith-auth-002"
    key = b"k" * 32
    seal_arithmetic_run(root, claim.claim_id, key)
    with pytest.raises(ValueError, match="attestation_mac_invalid"):
        verify_scheduled_arithmetic(root, claim, attestation_key=b"x" * 32)
    assert not (
        root / "claims" / claim.claim_id / "verification_receipt.json"
    ).exists()
