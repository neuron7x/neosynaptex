from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal


def test_unaffordable_verify_records_unmet_need_and_consistent_status(tmp_path):
    ctx = ConstructContext(True, True, False, False, True, True)
    claims = [ClaimSignal(str(i), 0.99, 0.99, 0.99, 0.7, 0.1, 0.5) for i in range(40)]
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, tmp_path, ctx)
    assert isinstance(res, Ok)
    out = res.value
    flagged = [r for r in out["routes"] if r["unmet_verification_need"]]
    assert flagged
    assert all(r["desired_route_mode"] in ("verify", "escalate") for r in flagged)
    assert all(r["final_status"] in ("CHEAP_TRIAGE", "QUARANTINED") for r in flagged)
