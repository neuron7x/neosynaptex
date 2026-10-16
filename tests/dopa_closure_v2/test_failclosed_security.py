"""Adversarial regression contracts for closure integrity and budget safety."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.eai.dopa_artifacts import claim_artifact_name
from core.eai.dopa_budget import BudgetLedger
from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Err, Ok
from core.eai.dopa_types import ClaimSignal

CONFIG = "configs/dopa_closure_v2/allocator.yaml"
DECLARED = ConstructContext(True, True, False, False, True, True)


def _verifiable_risk_proxy() -> ClaimSignal:
    # Deliberately low evidence risk, high enough priority for VERIFY.
    # Low risk alone MUST NOT imply correctness or CLOSED.
    return ClaimSignal("claim", 0.6, 0.7, 0.6, 0.1, 0.8, 0.55)


def test_never_close_without_independent_verifier(tmp_path: Path) -> None:
    res = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(res, Ok)
    output = res.value
    assert output["final_verdict"] == "INADMISSIBLE"
    assert "independent_verifier_not_executed" in output["failure_reasons"]
    assert "construct_context_not_independently_attested" in output["failure_reasons"]
    route = output["routes"][0]
    assert route["desired_route_mode"] == "verify"
    assert route["route_mode"] == "verify"
    assert route["final_status"] == "VERIFY"
    assert route["verification_result"] == "not_run"
    assert route["verification_artifact_hash"] is None
    assert not (tmp_path / "runs" / output["run_id"] / "claims"
                / "claim" / "closure_artifact.json").exists()
    request = (tmp_path / "runs" / output["run_id"] / "claims"
               / "claim" / "verification_request.json")
    assert request.exists()
    record = json.loads(request.read_text(encoding="utf-8"))
    assert record["verification_result"] == "not_run"


def test_no_all_ones_context_can_attest_verification(tmp_path: Path) -> None:
    res = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(res, Ok)
    assert res.value["construct_gate"]["admissible"] is True
    # The construct gate permits routing, not truth/evidence promotion.
    assert res.value["final_verdict"] == "INADMISSIBLE"


def test_duplicate_claim_ids_rejected_before_any_write(tmp_path: Path) -> None:
    claim = _verifiable_risk_proxy()
    res = run_allocator_full_path(CONFIG, [claim, claim], tmp_path, DECLARED)
    assert isinstance(res, Err)
    assert res.reason == "duplicate_claim_ids"
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("run_id", ["../escape", "../../", "x/y", ".", "..",
                                   "a" * 129, "bad\\path"])
def test_arbitrary_run_id_cannot_escape_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_id: str
) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", run_id)
    res = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(res, Err)
    assert res.reason == "invalid_run_id"
    assert not (tmp_path / "runs").exists()


def test_run_id_collision_refuses_to_overwrite_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOPA_RUN_ID", "fixed-test-id")
    first = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(first, Ok)
    run_dir = tmp_path / "runs" / "fixed-test-id"
    target = run_dir / "final_verdict.json"
    before = target.read_bytes()
    second = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(second, Err)
    assert second.reason == "run_id_collision"
    assert target.read_bytes() == before


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), float("-inf")])
def test_nonfinite_or_negative_budgets_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        BudgetLedger.create(bad, 0.1)
    with pytest.raises(ValueError):
        BudgetLedger.create(10.0, bad)
    with pytest.raises(ValueError):
        BudgetLedger.create(10.0, 0.1, bad)


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), float("-inf")])
def test_nonfinite_or_negative_requests_never_mutate_ledger(bad: float) -> None:
    ledger = BudgetLedger.create(10.0, 1.0)
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        ledger.apply(bad, 0.5)
    with pytest.raises(ValueError):
        ledger.apply(1.0, bad)
    assert ledger.snapshot() == before


def test_extreme_penalty_fails_closed_without_overflow() -> None:
    ledger = BudgetLedger.create(10.0, 1.0, lambda_penalty=1.0)
    ledger.failure_streak = 10_000
    step = ledger.apply(3.0, 2.0)
    assert step.overspend
    assert step.action_cost == pytest.approx(3.0)
    assert step.after == pytest.approx(7.0)
    assert ledger.snapshot()["conserved"] is True


def test_direct_budget_state_must_obey_invariants() -> None:
    with pytest.raises(ValueError):
        BudgetLedger(
            Decimal("10"), Decimal("0"), Decimal("20"), 0, 0.0
        )
    with pytest.raises(ValueError):
        BudgetLedger(
            Decimal("NaN"), Decimal("0"), Decimal("0"), 0, 0.0
        )


def test_artifact_names_preserve_epistemic_status() -> None:
    assert claim_artifact_name("verify", "VERIFY") == "verification_request.json"
    assert claim_artifact_name("cheap_triage", "CHEAP_TRIAGE") == "triage_request.json"
    assert claim_artifact_name("verify", "CLOSED") == "closure_artifact.json"


def test_failed_construct_no_closure(tmp_path: Path) -> None:
    denied = ConstructContext(False, True, False, False, True, True)
    res = run_allocator_full_path(CONFIG, [_verifiable_risk_proxy()], tmp_path, denied)
    assert isinstance(res, Ok)
    assert res.value["final_verdict"] == "INSTRUMENT_INADMISSIBLE"
    assert res.value["routes"] == []


def test_yaml_nonfinite_numbers_are_blocked(tmp_path: Path) -> None:
    src = Path(CONFIG).read_text(encoding="utf-8")
    modified = src.replace("load_center: 0.55", "load_center: .nan")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(modified, encoding="utf-8")
    result = run_allocator_full_path(cfg, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(result, Err)
    assert "nonfinite_number" in result.reason
    assert not (tmp_path / "runs").exists()


def test_yaml_threshold_order_and_missing_cost_are_blocked(tmp_path: Path) -> None:
    src = Path(CONFIG).read_text(encoding="utf-8")
    wrong_order = src.replace("    verify: 0.44", "    verify: 0.90")
    path = tmp_path / "bad-order.yaml"
    path.write_text(wrong_order, encoding="utf-8")
    result = run_allocator_full_path(path, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(result, Err)
    assert "routing_thresholds_out_of_order" in result.reason
    missing_cost = src.replace("    quarantine: 2.0\n", "")
    path.write_text(missing_cost, encoding="utf-8")
    result = run_allocator_full_path(path, [_verifiable_risk_proxy()], tmp_path, DECLARED)
    assert isinstance(result, Err)
    assert "missing_action_cost:quarantine" in result.reason


def test_config_snapshot_rejects_toctou_hash_drift(tmp_path: Path) -> None:
    import hashlib

    from core.eai.dopa_closure_v2 import _write_config_snapshot

    cfg = tmp_path / "config.yaml"
    cfg.write_text("key: old\n", encoding="utf-8")
    correct_hash = hashlib.sha256(cfg.read_bytes()).hexdigest()
    cfg.write_text("key: new\n", encoding="utf-8")
    with pytest.raises(ValueError, match="config_snapshot_hash_mismatch"):
        _write_config_snapshot(tmp_path, cfg, correct_hash)
    assert not (tmp_path / "config.sha256").exists()
