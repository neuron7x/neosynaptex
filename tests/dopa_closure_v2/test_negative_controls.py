from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal


def test_controls_execute_and_emit_pass_flag(tmp_path):
    ctx = ConstructContext(True, True, False, False, True, True)
    claims = [ClaimSignal("c", 0.8, 0.8, 0.8, 0.3, 0.7, 0.5)]
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, tmp_path, ctx)
    assert isinstance(res, Ok)
    out = res.value
    assert "passed" in out["controls"]
