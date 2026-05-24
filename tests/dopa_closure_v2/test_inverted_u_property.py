from core.eai.dopa_closure_v2 import DopaClosureV2Allocator
from core.eai.dopa_types import ClaimSignal


def _claim(claim_id: str, load: float) -> ClaimSignal:
    return ClaimSignal(claim_id, 0.7, 0.6, 0.5, 0.4, 0.7, load)


def test_inverted_u_peak_property_sweep() -> None:
    allocator = DopaClosureV2Allocator("configs/dopa_closure_v2/allocator.yaml")
    mid = allocator.priority_of_verification(_claim("m", 0.55))
    for i in range(101):
        load = i / 100
        claim_id = "c" + str(i)
        priority = allocator.priority_of_verification(_claim(claim_id, load))
        assert priority <= mid + 1e-12
