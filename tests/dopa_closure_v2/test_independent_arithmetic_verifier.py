"""Offline adversarial tests: independent arithmetic proof boundary."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.eai.dopa_independent_verifier import (
    ArithmeticClaim, arithmetic_commitment, verify_scheduled_arithmetic,
)


@pytest.fixture
def fixture_run(tmp_path: Path):
    def build(claim: ArithmeticClaim, **overrides):
        root = tmp_path / "runs" / "run-A01"
        root.mkdir(parents=True, exist_ok=True)
        route = {
            "claim_id": claim.claim_id,
            "claim_payload_sha256": arithmetic_commitment(claim),
            "route_mode": "verify", "final_status": "VERIFY",
            "verification_result": "not_run", "unmet_verification_need": False,
            "budget": {"overspend": False}, "config_hash": "c" * 64,
        }
        route.update(overrides)
        d = root / "claims" / claim.claim_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "route.json").write_text(json.dumps(route), encoding="utf-8")
        report = {"run_id": root.name, "config_hash": "c" * 64,
                  "final_verdict": "INADMISSIBLE", "routes": [route]}
        (root / "final_verdict.json").write_text(json.dumps(report), encoding="utf-8")
        return root
    return build


def c(asserted: int = 12) -> ArithmeticClaim:
    return ArithmeticClaim("A-01", "multiply", 3, 4, asserted)


def test_correct_exact_recomputation(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim)
    receipt = verify_scheduled_arithmetic(root, claim)
    assert receipt["verdict"] == "VERIFIED"
    assert receipt["computed"] == 12
    assert receipt["claim_payload_sha256"] == arithmetic_commitment(claim)
    assert json.loads((root/"claims"/"A-01"/"verification_receipt.json").read_text()) == receipt
    assert json.loads((root/"final_verdict.json").read_text())["final_verdict"] == "INADMISSIBLE"


def test_incorrect_arithmetic_is_refuted(fixture_run) -> None:
    claim = c(13)
    receipt = verify_scheduled_arithmetic(fixture_run(claim), claim)
    assert receipt["verdict"] == "REFUTED"
    assert receipt["computed"] == 12


def test_subtract_and_add_are_exact(fixture_run) -> None:
    for operation, lhs, rhs, expected in [("add", 8, -3, 5), ("subtract", 8, -3, 11)]:
        claim = ArithmeticClaim(operation, operation, lhs, rhs, expected)
        root = fixture_run(claim)
        assert verify_scheduled_arithmetic(root, claim)["verdict"] == "VERIFIED"


def test_unbound_claim_payload_fails(fixture_run) -> None:
    root = fixture_run(c())
    with pytest.raises(ValueError, match="claim_payload_commitment_mismatch"):
        verify_scheduled_arithmetic(root, c(13))


def test_tampered_route_file_fails(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim)
    p = root/"claims"/"A-01"/"route.json"
    route = json.loads(p.read_text())
    route["claim_payload_sha256"] = "1" * 64
    p.write_text(json.dumps(route))
    with pytest.raises(ValueError, match="route_report_mismatch"):
        verify_scheduled_arithmetic(root, claim)


def test_no_duplicate_receipt_can_replace_first(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim)
    first = verify_scheduled_arithmetic(root, claim)
    p = root/"claims"/"A-01"/"verification_receipt.json"
    before = p.read_bytes()
    with pytest.raises(FileExistsError):
        verify_scheduled_arithmetic(root, claim)
    assert p.read_bytes() == before
    assert first["verdict"] == "VERIFIED"


@pytest.mark.parametrize("route", [
    {"route_mode": "cheap_triage"},
    {"route_mode": "quarantine"},
    {"unmet_verification_need": True},
    {"budget": {"overspend": True}},
    {"verification_result": "pass"},
    {"final_status": "CLOSED"},
])
def test_wrong_route_or_budget_fails(fixture_run, route) -> None:
    claim = c()
    with pytest.raises(ValueError):
        verify_scheduled_arithmetic(fixture_run(claim, **route), claim)


@pytest.mark.parametrize("claim", [
    ("../../bad", "add", 1, 2, 3),
    ("claim", "eval", 1, 2, 3),
    ("claim", "add", True, 2, 3),
    ("claim", "add", 10**12, 2, 3),
])
def test_bad_input_denied(claim) -> None:
    with pytest.raises(ValueError):
        ArithmeticClaim(*claim)


def test_duplicate_json_keys_denied(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim)
    p = root/"final_verdict.json"
    p.write_text('{"run_id":"run-A01","run_id":"run-A01"}')
    with pytest.raises(ValueError, match="duplicate_json_key"):
        verify_scheduled_arithmetic(root, claim)


def test_symlink_route_denied(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim)
    route = root/"claims"/"A-01"/"route.json"
    orig = route.with_name("legit.json")
    route.rename(orig)
    route.symlink_to(orig)
    with pytest.raises(ValueError, match="untrusted_or_oversize_evidence"):
        verify_scheduled_arithmetic(root, claim)


def test_no_commitment_is_denied(fixture_run) -> None:
    claim = c()
    root = fixture_run(claim, claim_payload_sha256=None)
    with pytest.raises(ValueError, match="claim_payload_commitment_mismatch"):
        verify_scheduled_arithmetic(root, claim)
