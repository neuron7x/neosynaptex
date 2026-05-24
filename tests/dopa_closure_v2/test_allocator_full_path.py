from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from core.eai.dopa_closure_v2 import DopaClosureV2Allocator, run_allocator_full_path
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Ok
from core.eai.dopa_types import ClaimSignal

CONFIG_PATH = "configs/dopa_closure_v2/allocator.yaml"


def _claims() -> list[ClaimSignal]:
    return [
        ClaimSignal("c1", 0.7, 0.8, 0.4, 0.2, 0.9, 0.5),
        ClaimSignal("c2", 0.9, 0.9, 0.8, 0.97, 0.3, 0.5),
        ClaimSignal("c3", 0.3, 0.3, 0.2, 0.1, 0.9, 1.0),
    ]


def test_full_path_and_schema(tmp_path: Path) -> None:
    ctx = ConstructContext(True, True, False, False, True, True)
    res = run_allocator_full_path(CONFIG_PATH, _claims(), tmp_path, ctx)
    assert isinstance(res, Ok)
    result = res.value
    schema = json.loads(Path("schemas/dopa_closure_v2_result.schema.json").read_text())
    validate(result, schema)
    assert result["budget_ledger"]["conserved"] is True
    assert all("route_mode" in r for r in result["routes"])


def test_inadmissible_construct_blocks_routing(tmp_path: Path) -> None:
    ctx = ConstructContext(False, True, False, False, True, True)
    res = run_allocator_full_path(CONFIG_PATH, _claims(), tmp_path, ctx)
    assert isinstance(res, Ok)
    result = res.value
    assert result["final_verdict"] == "INSTRUMENT_INADMISSIBLE"


def test_inverted_u_non_monotone() -> None:
    a = DopaClosureV2Allocator(CONFIG_PATH)
    low = a.priority_of_verification(ClaimSignal("x", 0.6, 0.6, 0.6, 0.6, 0.6, 0.0))
    mid = a.priority_of_verification(ClaimSignal("y", 0.6, 0.6, 0.6, 0.6, 0.6, 0.55))
    high = a.priority_of_verification(ClaimSignal("z", 0.6, 0.6, 0.6, 0.6, 0.6, 1.0))
    assert mid > low
    assert mid > high
