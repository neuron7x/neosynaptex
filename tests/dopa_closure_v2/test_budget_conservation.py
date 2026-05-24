from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal


def test_budget_conserved_and_no_negative_remaining(tmp_path):
    ctx = ConstructContext(True, True, False, False, True, True)
    claims = [ClaimSignal(str(i), 0.9, 0.9, 0.9, 0.2, 0.1, 0.5) for i in range(30)]
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, tmp_path, ctx)
    assert isinstance(res, Ok)
    out = res.value
    assert out["budget_ledger"]["conserved"] is True
    assert out["budget_ledger"]["remaining"] >= 0
