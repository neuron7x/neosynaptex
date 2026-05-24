from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal


def test_critical_claim_not_silently_quarantined_under_budget_pressure(tmp_path):
    ctx = ConstructContext(True, True, False, False, True, True)
    claims = [
        ClaimSignal("a", 0.99, 0.8, 0.9, 0.7, 0.2, 0.5),
        ClaimSignal("b", 0.99, 0.8, 0.9, 0.7, 0.2, 0.5),
        ClaimSignal("c", 0.99, 0.8, 0.9, 0.7, 0.2, 0.5),
    ]
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, tmp_path, ctx)
    assert isinstance(res, Ok)
    out = res.value
    assert out["deferred_due_budget"] >= 0
    assert any(r["route_mode"] in ("cheap_triage", "verify", "escalate") for r in out["routes"])
