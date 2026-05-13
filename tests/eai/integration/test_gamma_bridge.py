"""Tests for the γ-ledger → EAI gate bridge.

Pins the mapping invariants:
- A clean EVIDENCE_CANDIDATE with valid data_sha256 → gate EVIDENCE.
- An EVIDENCE_CANDIDATE with missing data_sha256 → gate QUARANTINED
  (hash binding withheld; revalidation withheld).
- An EVIDENCE_CANDIDATE_NULL_FAILED → gate KILLED via the
  ``null_screen_rejected`` contradiction marker.
- LOCAL_STRUCTURAL_EVIDENCE_ONLY → gate KILLED via
  ``local_structural_only``.
- NUMERICAL_INTERNAL tier → gate KILLED via ``numerical_internal_only``.
- Bridge is read-only: input ledger entry dicts are not mutated.
- Bridge is deterministic: same input produces byte-identical output.
- Full ledger run is byte-deterministic.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from core.artifact_ledger import ArtifactLedger
from core.eai.engine import EAIEngine
from core.eai.gamma_bridge import (
    GammaGateInputs,
    ledger_entry_to_gate_inputs,
    load_ledger,
)
from core.integration_memory import IntegrationMemory
from tools.eai.run_gamma_ledger_through_gate import run_bridge

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _REPO_ROOT / "evidence" / "gamma_ledger.json"
_BRIDGE_MODULE = _REPO_ROOT / "core" / "eai" / "gamma_bridge.py"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _clean_entry() -> dict[str, object]:
    return {
        "substrate": "synthetic_clean",
        "description": "Synthetic clean γ measurement on bench T.",
        "status": "EVIDENCE_CANDIDATE",
        "evidence_tier": "MEASURED_WITH_HASH",
        "data_sha256": "a" * 64,
        "derivation_method": "synthetic_bench_v1",
        "rerun_command": "make synthetic-clean",
    }


def _nohash_entry() -> dict[str, object]:
    e = _clean_entry()
    e["data_sha256"] = None
    e["evidence_tier"] = "MEASURED_NO_HASH"
    return e


def _null_failed_entry() -> dict[str, object]:
    e = _clean_entry()
    e["status"] = "EVIDENCE_CANDIDATE_NULL_FAILED"
    return e


def _local_structural_entry() -> dict[str, object]:
    e = _clean_entry()
    e["status"] = "LOCAL_STRUCTURAL_EVIDENCE_ONLY"
    e["evidence_tier"] = "LOCAL_STRUCTURAL"
    return e


def _numerical_internal_entry() -> dict[str, object]:
    e = _clean_entry()
    e["evidence_tier"] = "NUMERICAL_INTERNAL"
    return e


def _frozen_clock() -> str:
    return "1970-01-01T00:00:00+00:00"


def _run_through_engine(inputs: GammaGateInputs) -> str:
    engine = EAIEngine(ledger=ArtifactLedger(clock=_frozen_clock), memory=IntegrationMemory())
    outcome = engine.run_candidate(
        claim=inputs.claim,
        boundary=inputs.boundary,
        contradiction_markers=inputs.contradiction_markers,
        reproducibility=inputs.reproducibility,
        retention_hash=inputs.retention_hash,
        revalidation_passed=inputs.revalidation_passed,
        integration_patch={"guardrail_update": {"id": "GR-TEST"}},
        next_intent_delta={"delta": 1},
    )
    return outcome.status.value


def test_clean_hash_bound_entry_promotes_to_evidence() -> None:
    inputs = ledger_entry_to_gate_inputs("k", _clean_entry(), ledger_version="2.0.0")
    assert inputs.hash_bound is True
    assert inputs.status_tags == []
    assert inputs.revalidation_passed is True
    assert _run_through_engine(inputs) == "EVIDENCE"


def test_missing_hash_routes_to_quarantine() -> None:
    inputs = ledger_entry_to_gate_inputs("k", _nohash_entry(), ledger_version="2.0.0")
    assert inputs.hash_bound is False
    assert inputs.status_tags == []
    assert inputs.revalidation_passed is False
    assert _SHA256_HEX.fullmatch(inputs.reproducibility.artifact_hash)
    assert _run_through_engine(inputs) == "QUARANTINED"


def test_null_failed_entry_routes_to_killed_via_falsifier() -> None:
    inputs = ledger_entry_to_gate_inputs("k", _null_failed_entry(), ledger_version="2.0.0")
    assert "null_screen_rejected" in inputs.status_tags
    assert "null_screen_rejected" in inputs.claim.claim_text
    assert "null_screen_rejected" in inputs.contradiction_markers
    assert _run_through_engine(inputs) == "KILLED"


def test_local_structural_routes_to_killed() -> None:
    inputs = ledger_entry_to_gate_inputs("k", _local_structural_entry(), ledger_version="2.0.0")
    assert "local_structural_only" in inputs.status_tags
    assert _run_through_engine(inputs) == "KILLED"


def test_numerical_internal_routes_to_killed() -> None:
    inputs = ledger_entry_to_gate_inputs("k", _numerical_internal_entry(), ledger_version="2.0.0")
    assert "numerical_internal_only" in inputs.status_tags
    assert _run_through_engine(inputs) == "KILLED"


def test_bridge_does_not_mutate_input_entry() -> None:
    entry = _clean_entry()
    snapshot = copy.deepcopy(entry)
    ledger_entry_to_gate_inputs("k", entry, ledger_version="2.0.0")
    assert entry == snapshot


def test_mapping_is_deterministic() -> None:
    a = ledger_entry_to_gate_inputs("k", _clean_entry(), ledger_version="2.0.0")
    b = ledger_entry_to_gate_inputs("k", _clean_entry(), ledger_version="2.0.0")
    assert a == b


def test_fallback_artifact_hash_is_valid_sha256_and_deterministic() -> None:
    inputs_a = ledger_entry_to_gate_inputs("k", _nohash_entry(), ledger_version="2.0.0")
    inputs_b = ledger_entry_to_gate_inputs("k", _nohash_entry(), ledger_version="2.0.0")
    assert inputs_a.reproducibility.artifact_hash == inputs_b.reproducibility.artifact_hash
    assert _SHA256_HEX.fullmatch(inputs_a.reproducibility.artifact_hash)


def test_full_ledger_run_is_byte_deterministic() -> None:
    a = run_bridge(_LEDGER, _BRIDGE_MODULE)
    b = run_bridge(_LEDGER, _BRIDGE_MODULE)
    assert a == b
    # Stable header fields
    assert a["schema_version"] == "EAI-GAMMA-BRIDGE-v1"
    assert a["frozen_clock"] == "1970-01-01T00:00:00+00:00"
    assert _SHA256_HEX.fullmatch(a["ledger_sha256"])
    assert _SHA256_HEX.fullmatch(a["bridge_module_sha256"])


def test_full_ledger_run_produces_nonzero_admissibility_signal() -> None:
    report = run_bridge(_LEDGER, _BRIDGE_MODULE)
    # The bridge MUST produce a non-degenerate distribution: at least
    # one verdict in each of {EVIDENCE, KILLED, QUARANTINED} given
    # the current ledger composition.
    verdicts = report["gate_verdict_counts"]
    assert verdicts.get("EVIDENCE", 0) >= 1, verdicts
    assert verdicts.get("KILLED", 0) >= 1, verdicts
    assert verdicts.get("QUARANTINED", 0) >= 1, verdicts
    # Counts must sum to total_entries (no entry lost).
    assert sum(verdicts.values()) == report["total_entries"]


def test_load_ledger_returns_version_and_entries_dict() -> None:
    version, entries = load_ledger(_LEDGER)
    assert version
    assert isinstance(entries, dict)
    assert len(entries) > 0
    # Spot-check known keys
    assert "eeg_physionet" in entries or "zebrafish_wt" in entries


def test_report_per_entry_records_ledger_and_gate_metadata() -> None:
    report = run_bridge(_LEDGER, _BRIDGE_MODULE)
    for entry in report["per_entry"]:
        assert entry["ledger_key"]
        assert entry["substrate"]
        assert entry["ledger_status"]
        assert entry["gate_status"] in {"EVIDENCE", "KILLED", "QUARANTINED"}
        assert isinstance(entry["status_tags"], list)
        assert isinstance(entry["hash_bound"], bool)
        assert _SHA256_HEX.fullmatch(entry["retention_hash"])


def test_admissibility_rate_matches_counts() -> None:
    report = run_bridge(_LEDGER, _BRIDGE_MODULE)
    expected = (
        report["admissible_evidence"] / report["candidate_total"]
        if report["candidate_total"]
        else 0.0
    )
    assert round(expected, 6) == report["admissibility_rate"]


def test_dataset_sha256_is_real_file_digest() -> None:
    report = run_bridge(_LEDGER, _BRIDGE_MODULE)
    expected = hashlib.sha256(_LEDGER.read_bytes()).hexdigest()
    assert report["ledger_sha256"] == expected


def test_report_can_be_json_serialised() -> None:
    report = run_bridge(_LEDGER, _BRIDGE_MODULE)
    payload = json.dumps(report, sort_keys=True)
    assert "schema_version" in payload
    assert "per_entry" in payload
