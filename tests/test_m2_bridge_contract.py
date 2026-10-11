"""Tests for the M2 pre-registration contract (PR M2.5).

The contract `contracts/M2_BRIDGE_EXPERIMENT_PRE_REGISTRATION.yaml`
defines two mutually exclusive experiment paths with frozen
thresholds and nulls. PR M2.5 only locks the contract; no
measurement runs here. These tests verify that the contract is
parseable, both paths are fully specified, all required verdicts
exist, no threshold is `TBD`, and no contracted measurement output
exists yet.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "contracts" / "M2_BRIDGE_EXPERIMENT_PRE_REGISTRATION.yaml"
RESULTS_ROOT = REPO_ROOT / "results"


def _load() -> dict[str, object]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def test_contract_file_exists() -> None:
    assert CONTRACT_PATH.exists(), f"missing {CONTRACT_PATH}"


def test_contract_parses() -> None:
    data = _load()
    assert isinstance(data, dict), "contract top-level must be a mapping"


def test_contract_top_level_keys() -> None:
    data = _load()
    for key in (
        "contract_id",
        "schema_version",
        "status",
        "claim_status",
        "global_rules",
        "paths",
        "evidence_artifacts",
        "implementation_gates",
        "reproducibility",
    ):
        assert key in data, f"contract missing top-level key: {key}"
    assert data["contract_id"] == "M2_BRIDGE_EXPERIMENT_PRE_REGISTRATION"
    assert data["status"] == "pre_registered"
    assert data["claim_status"] == "derived"


def test_two_paths_exist() -> None:
    data = _load()
    paths = data["paths"]
    assert isinstance(paths, list)
    assert len(paths) == 2, f"expected exactly 2 mutually exclusive paths, got {len(paths)}"
    ids = {p["id"] for p in paths}
    assert ids == {"BNSYN_2D_SPATIAL_HWI", "SCALE_INVARIANT_OPERATOR_BRIDGE"}


@pytest.mark.parametrize(
    "path_id",
    ["BNSYN_2D_SPATIAL_HWI", "SCALE_INVARIANT_OPERATOR_BRIDGE"],
)
def test_each_path_has_required_verdicts(path_id: str) -> None:
    data = _load()
    path = next(p for p in data["paths"] if p["id"] == path_id)
    verdicts = path.get("verdicts")
    assert isinstance(verdicts, dict)
    for required in (
        "PASS",
        "FAIL_OFFBAND",
        "FAIL_NULL_LEAK",
        "INVALID_OPERATOR",
        "INVALID_PRECONDITION",
    ):
        assert required in verdicts, f"path {path_id} missing verdict: {required}"
        v = verdicts[required]
        assert "condition" in v and "interpretation" in v, (
            f"verdict {required} on path {path_id} missing condition/interpretation"
        )


@pytest.mark.parametrize(
    "path_id",
    ["BNSYN_2D_SPATIAL_HWI", "SCALE_INVARIANT_OPERATOR_BRIDGE"],
)
def test_each_path_has_preconditions(path_id: str) -> None:
    data = _load()
    path = next(p for p in data["paths"] if p["id"] == path_id)
    preconds = path.get("preconditions")
    assert isinstance(preconds, list) and preconds, (
        f"path {path_id} preconditions must be a non-empty list"
    )


@pytest.mark.parametrize(
    "path_id",
    ["BNSYN_2D_SPATIAL_HWI", "SCALE_INVARIANT_OPERATOR_BRIDGE"],
)
def test_each_path_has_null_band_test(path_id: str) -> None:
    data = _load()
    path = next(p for p in data["paths"] if p["id"] == path_id)
    nbt = path.get("null_band_test")
    assert isinstance(nbt, dict) and nbt, f"path {path_id} null_band_test must be defined"


def test_global_rules_forbid_threshold_widening() -> None:
    data = _load()
    rules = data["global_rules"]
    assert rules["thresholds_locked_before_measurement"] is True
    assert rules["no_threshold_field_may_be_TBD"] is True
    forbidden = rules["forbidden_post_hoc_actions"]
    assert any("widening" in s.lower() for s in forbidden), (
        "global_rules.forbidden_post_hoc_actions must explicitly forbid widening any threshold"
    )


def test_no_threshold_field_is_tbd() -> None:
    """Walk the contract recursively and assert no threshold-bearing
    string equals 'TBD' (case-insensitive)."""
    data = _load()

    def walk(node: object, trail: str = "") -> list[str]:
        bad: list[str] = []
        if isinstance(node, dict):
            for k, v in node.items():
                bad.extend(walk(v, f"{trail}.{k}"))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                bad.extend(walk(v, f"{trail}[{i}]"))
        elif isinstance(node, str) and node.strip().upper() == "TBD":
            bad.append(trail)
        return bad

    tbd_locations = walk(data)
    assert not tbd_locations, f"contract has TBD fields: {tbd_locations}"


def test_no_contracted_measurement_output_yet() -> None:
    """PR M2.5 locks the contract only; the run JSONs declared at
    `evidence_artifacts.json_path_*` must NOT exist yet."""
    data = _load()
    artifacts = data["evidence_artifacts"]
    for key in ("json_path_path_a", "json_path_path_b"):
        rel = artifacts[key]
        target = REPO_ROOT / rel
        assert not target.exists(), (
            f"contracted measurement output {target} must not exist in PR M2.5 — "
            "that is the responsibility of PR M2.7"
        )


def test_global_seed_list_frozen() -> None:
    data = _load()
    rules = data["global_rules"]
    seeds = rules.get("global_seed_list")
    assert seeds == [42, 43, 44, 45, 46], f"seed list must be locked at [42..46]; got {seeds}"
    assert rules.get("global_n_seeds") == len(seeds)


def test_evidence_artifacts_paths_under_results() -> None:
    data = _load()
    artifacts = data["evidence_artifacts"]
    for key in ("json_path_path_a", "json_path_path_b"):
        rel = artifacts[key]
        # mirrors the convention used by PR #171: results/<experiment>/run_v1.json
        assert rel.startswith("results/"), (
            f"evidence path {rel!r} must live under results/ to avoid the "
            "evidence/ pre-commit ledger gate"
        )
        assert rel.endswith(".json")


def test_implementation_gates_block_m2_7_until_m2_6() -> None:
    data = _load()
    gates = data["implementation_gates"]
    before_m2_7 = gates["before_M2_7_contracted_measurement"]
    assert any("M2.6" in s or "M2_6" in s for s in before_m2_7), (
        "M2.7 must be gated on M2.6 having merged"
    )


def test_path_a_uses_unmodified_mfn_operator() -> None:
    data = _load()
    path = next(p for p in data["paths"] if p["id"] == "BNSYN_2D_SPATIAL_HWI")
    assert path["operator"].endswith("compute_hwi_components"), (
        "Path A must reuse MFN's existing 2-D operator"
    )
    assert path["operator_modification"] == "forbidden"


def test_path_b_pairs_geometry_and_manifold_free() -> None:
    data = _load()
    path = next(p for p in data["paths"] if p["id"] == "SCALE_INVARIANT_OPERATOR_BRIDGE")
    assert path["primary_operator"] == "sinkhorn_debiased"
    assert path["secondary_operator"] == "js_trajectory_divergence"


def test_global_rules_forbid_substrate_dynamics_modification() -> None:
    data = _load()
    rules = data["global_rules"]
    forbidden = rules.get("forbidden_substrate_modification")
    assert isinstance(forbidden, list) and forbidden
    text = " ".join(forbidden).lower()
    assert "bn_syn" in text and "mfn" in text, (
        "forbidden_substrate_modification must mention both BN-Syn and MFN"
    )
