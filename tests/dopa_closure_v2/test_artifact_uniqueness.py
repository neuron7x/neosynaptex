from pathlib import Path

from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_types import ClaimSignal


def test_per_claim_artifacts(tmp_path: Path) -> None:
    ctx = ConstructContext(True, True, False, False, True, True)
    claims = [
        ClaimSignal("a", 0.6, 0.6, 0.6, 0.1, 0.6, 0.5),
        ClaimSignal("b", 0.6, 0.6, 0.6, 0.1, 0.6, 0.5),
    ]
    run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, tmp_path, ctx)
    runs = list((tmp_path / "runs").iterdir())
    assert runs
    assert (runs[0] / "claims" / "a" / "route.json").exists()
    assert (runs[0] / "claims" / "b" / "route.json").exists()
