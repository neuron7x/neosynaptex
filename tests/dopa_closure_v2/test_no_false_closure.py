from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal


def test_no_false_closure(tmp_path):
    ctx = ConstructContext(True, True, False, False, True, True)
    claim = ClaimSignal("q", 0.9, 0.9, 0.9, 0.8, 0.2, 0.5)
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", [claim], tmp_path, ctx)
    assert isinstance(res, Ok)
    out = res.value
    route = out["routes"][0]
    if route["final_status"] == "CLOSED":
        assert route["verification_result"] == "pass"
