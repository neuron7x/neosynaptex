#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal, FinalStatus, RouteMode


def execute_matrix_verification() -> int:
    base = Path(__file__).resolve().parents[1]
    cfg = base / "configs" / "dopa_closure_v2" / "allocator.yaml"
    outdir = base / "artifacts" / "dopa_closure_verification"

    claims = [
        ClaimSignal("anomaly-max-01", 1.0, 1.0, 1.0, 0.5, 0.0, 0.55),
        ClaimSignal("gauss-deadzone-02", 1.0, 1.0, 1.0, 0.1, 0.0, 1.0),
        ClaimSignal("fast-reject-03", 0.1, 0.1, 0.1, 0.98, 1.0, 0.55),
        ClaimSignal("budget-drain-04", 0.6, 0.5, 0.5, 0.2, 0.5, 0.55),
        ClaimSignal("budget-drain-05", 0.6, 0.5, 0.5, 0.2, 0.5, 0.55),
        ClaimSignal("budget-drain-06", 0.6, 0.5, 0.5, 0.2, 0.5, 0.55),
    ]
    ctx = ConstructContext(True, True, False, False, True, True)
    res = run_allocator_full_path(str(cfg), claims, str(outdir), ctx)
    if not isinstance(res, Ok):
        sys.stderr.write(f"CRITICAL_EXECUTION_FAILURE: {res.reason}\n")
        return 1

    data = res.value
    routes = {r["claim_id"]: r for r in data["routes"]}
    ledger = data["budget_ledger"]

    try:
        assert routes["anomaly-max-01"]["desired_route_mode"] == RouteMode.ESCALATE.value, "anomaly-max desired route"
        assert routes["gauss-deadzone-02"]["priority_of_verification"] <= 1e-8, "gauss deadzone priority non-zero"
        assert routes["gauss-deadzone-02"]["final_status"] == FinalStatus.QUARANTINED.value, "gauss deadzone not quarantined"
        assert routes["fast-reject-03"]["final_status"] == FinalStatus.REJECTED.value, "fast reject missed"
        assert ledger["conserved"] is True, "budget not conserved"
        assert data.get("deferred_due_budget", 0) >= 0
        assert any(r["desired_route_mode"] in (RouteMode.VERIFY.value, RouteMode.ESCALATE.value) for r in data["routes"])
    except AssertionError as exc:
        sys.stderr.write(f"SYSTEM_DESIGN_FALSIFIED: {exc}\n")
        return 1

    report = {
        "run_id": data["run_id"],
        "final_verdict": data["final_verdict"],
        "ledger_summary": {
            "initial_envelope": ledger["envelope"],
            "remaining_balance": ledger["remaining"],
            "law_of_conservation_verified": ledger["conserved"],
        },
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(execute_matrix_verification())
