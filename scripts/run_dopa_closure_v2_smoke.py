from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.eai.dopa_closure_v2 import run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_types import ClaimSignal
from core.eai.dopa_result import Ok


def main() -> int:
    claims = [
        ClaimSignal("smoke-1", 0.8, 0.7, 0.6, 0.2, 0.8, 0.5),
        ClaimSignal("smoke-2", 0.9, 0.7, 0.7, 0.99, 0.2, 0.5),
    ]
    ctx = ConstructContext(True, True, False, False, True, True)
    res = run_allocator_full_path("configs/dopa_closure_v2/allocator.yaml", claims, "artifacts/dopa_closure_v2", ctx)
    return 0 if isinstance(res, Ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
