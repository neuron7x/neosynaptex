"""Tests for `substrates.mycelium.method_gate` — Method Gate 0.

Eighteen tests covering the audit JSON loader, the cross-field validator,
the two boolean gates, JSON determinism / no-timestamp invariants, and
the partner audit document's required content.

These tests do NOT touch any biological data. They synthesise audit
JSON files in `tmp_path` for the loader/validator surface and read the
real repository artifacts only for the determinism, no-timestamp, and
audit-document content checks.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from substrates.mycelium.method_gate import (
    DEFINITION_NONE,
    STATUS_BLOCKED,
    STATUS_REJECTED,
    MethodGateResult,
    MethodGateValidation,
    can_promote_to_evidence_admissible,
    can_run_biological_pipeline,
    load_method_audit,
    validate_method_audit,
)

# ---------------------------------------------------------------------------
# Repository artifact paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_JSON_PATH = REPO_ROOT / "docs" / "methods" / "mycelium_gamma_definition_audit.json"
AUDIT_DOC_PATH = REPO_ROOT / "docs" / "methods" / "MYCELIUM_GAMMA_DEFINITION_AUDIT.md"


# ---------------------------------------------------------------------------
# Synthetic audit fixtures
# ---------------------------------------------------------------------------


def _blocked_payload() -> dict[str, Any]:
    """Minimal valid BLOCKED audit JSON."""
    return {
        "accepted_candidate_reason": "no candidate satisfies all four gates",
        "decision_reason": "canon does not yet specify mycelium electrophysiology",
        "forbidden_promotions": [
            "secondary metrics cannot promote the claim",
            "no data-driven metric switching",
            "no gamma definition changes after seeing fungal results",
            "no universality claim from this substrate alone",
        ],
        "gamma_target_interval": None,
        "h_tension_if_dfa": True,
        "method_risks": ["DFA cannot serve as primary"],
        "non_claims": [
            "This audit does not claim that mycelium is neural.",
            "This audit does not claim that mycelium is conscious.",
            (
                "This audit does not claim that fungal electrical activity "
                "proves gamma approximately 1.0."
            ),
            "This audit does not analyze fungal data.",
            "This audit does not prove universality.",
        ],
        "primary_gamma_definition": "NONE",
        "primary_metric_formula": "",
        "primary_metric_name": "",
        "rejected_candidates": [
            {
                "candidate": "DFA_2H_PLUS_1",
                "reason": "DFA secondary only",
            },
            {
                "candidate": "SPECTRAL_APERIODIC",
                "reason": "no fungal K and C operationalisations",
            },
        ],
        "secondary_metrics": ["DFA alpha (per §2.3 secondary cross-check only)"],
        "status": "BLOCKED_BY_METHOD_DEFINITION",
        "substrate_id": "SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY",
    }


def _accepted_spectral_payload() -> dict[str, Any]:
    """Hypothetical ACCEPTED payload using SPECTRAL_APERIODIC primary.

    The base BLOCKED fixture lists SPECTRAL_APERIODIC among rejected
    candidates; in the ACCEPTED variant we drop it from rejected so it
    appears only as primary (the loader forbids same-named primary +
    rejected coupling).
    """
    base = _blocked_payload()
    base["status"] = "GAMMA_DEFINITION_ACCEPTED"
    base["primary_gamma_definition"] = "SPECTRAL_APERIODIC"
    base["primary_metric_name"] = "FOOOF aperiodic exponent"
    base["primary_metric_formula"] = "PSD(f) ~ f^(-chi); gamma proxy = chi"
    base["gamma_target_interval"] = [0.9, 1.1]
    base["rejected_candidates"] = [
        entry for entry in base["rejected_candidates"] if entry["candidate"] != "SPECTRAL_APERIODIC"
    ]
    return base


def _write_payload(tmp_path: Path, payload: dict[str, Any], name: str = "audit.json") -> Path:
    target = tmp_path / name
    with target.open("w", encoding="ascii") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")
    return target


# ---------------------------------------------------------------------------
# 1. Loader: missing file -> FileNotFoundError
# ---------------------------------------------------------------------------


def test_01_load_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_method_audit(missing)


# ---------------------------------------------------------------------------
# 2. Loader: malformed JSON -> ValueError prefixed with INVALID_AUDIT_JSON:
# ---------------------------------------------------------------------------


def test_02_load_malformed_json_raises_value_error(tmp_path: Path) -> None:
    target = tmp_path / "bad.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_method_audit(target)
    assert str(exc_info.value).startswith("INVALID_AUDIT_JSON:")


# ---------------------------------------------------------------------------
# 3. Loader: missing required key -> ValueError
# ---------------------------------------------------------------------------


def test_03_load_missing_required_key_raises(tmp_path: Path) -> None:
    payload = _blocked_payload()
    del payload["substrate_id"]
    target = _write_payload(tmp_path, payload)
    with pytest.raises(ValueError) as exc_info:
        load_method_audit(target)
    assert "substrate_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Loader: wrong type for required key -> ValueError
# ---------------------------------------------------------------------------


def test_04_load_wrong_type_raises(tmp_path: Path) -> None:
    payload = _blocked_payload()
    payload["forbidden_promotions"] = "not-a-list"
    target = _write_payload(tmp_path, payload)
    with pytest.raises(ValueError) as exc_info:
        load_method_audit(target)
    assert "forbidden_promotions" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Loader: empty decision_reason -> ValueError
# ---------------------------------------------------------------------------


def test_05_load_empty_decision_reason_raises(tmp_path: Path) -> None:
    payload = _blocked_payload()
    payload["decision_reason"] = "   "
    target = _write_payload(tmp_path, payload)
    with pytest.raises(ValueError) as exc_info:
        load_method_audit(target)
    assert "decision_reason" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 6. Loader: duplicate rejected candidate (multiple primary definitions in
#    same file via duplicate entries) -> ValueError
# ---------------------------------------------------------------------------


def test_06_load_duplicate_rejected_candidate_raises(tmp_path: Path) -> None:
    payload = _blocked_payload()
    payload["rejected_candidates"] = [
        {"candidate": "DFA_2H_PLUS_1", "reason": "first"},
        {"candidate": "DFA_2H_PLUS_1", "reason": "second"},
    ]
    target = _write_payload(tmp_path, payload)
    with pytest.raises(ValueError) as exc_info:
        load_method_audit(target)
    assert "duplicate" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 7. Loader: invalid status string -> ValueError
# ---------------------------------------------------------------------------


def test_07_load_invalid_status_raises(tmp_path: Path) -> None:
    payload = _blocked_payload()
    payload["status"] = "DEFINITELY_FINE"
    target = _write_payload(tmp_path, payload)
    with pytest.raises(ValueError):
        load_method_audit(target)


# ---------------------------------------------------------------------------
# 8. Loader: real repository audit loads cleanly into MethodGateResult
# ---------------------------------------------------------------------------


def test_08_load_real_repo_audit_succeeds() -> None:
    result = load_method_audit(AUDIT_JSON_PATH)
    assert isinstance(result, MethodGateResult)
    assert result.substrate_id == "SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY"
    assert result.status == STATUS_BLOCKED
    assert result.primary_gamma_definition == DEFINITION_NONE


# ---------------------------------------------------------------------------
# 9. Validator: real repo audit -> valid (BLOCKED is the honest verdict)
# ---------------------------------------------------------------------------


def test_09_validate_real_repo_audit_is_valid() -> None:
    result = load_method_audit(AUDIT_JSON_PATH)
    validation = validate_method_audit(result)
    assert isinstance(validation, MethodGateValidation)
    assert validation.valid, f"unexpected errors: {validation.errors}"


# ---------------------------------------------------------------------------
# 10. Validator: NONE primary with non-BLOCKED status -> invalid
# ---------------------------------------------------------------------------


def test_10_validate_none_primary_requires_blocked_status(tmp_path: Path) -> None:
    payload = _blocked_payload()
    payload["status"] = STATUS_REJECTED  # NONE + REJECTED is forbidden
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    validation = validate_method_audit(result)
    assert not validation.valid
    assert any("NONE" in err for err in validation.errors)


# ---------------------------------------------------------------------------
# 11. Validator: ACCEPTED with empty primary_metric_formula -> invalid
# ---------------------------------------------------------------------------


def test_11_validate_accepted_requires_primary_metric_formula(tmp_path: Path) -> None:
    payload = _accepted_spectral_payload()
    payload["primary_metric_formula"] = ""
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    validation = validate_method_audit(result)
    assert not validation.valid
    assert any("primary_metric_formula" in err for err in validation.errors)


# ---------------------------------------------------------------------------
# 12. Validator: DFA candidate referenced with h_tension_if_dfa=None -> invalid
# ---------------------------------------------------------------------------


def test_12_validate_dfa_candidate_requires_h_tension_explicit(tmp_path: Path) -> None:
    payload = _blocked_payload()
    # DFA appears in rejected list per the default fixture; nullify the flag
    payload["h_tension_if_dfa"] = None
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    validation = validate_method_audit(result)
    assert not validation.valid
    assert any("h_tension_if_dfa" in err for err in validation.errors)


# ---------------------------------------------------------------------------
# 13. Gates: BLOCKED audit -> both gates return False
# ---------------------------------------------------------------------------


def test_13_gates_block_when_status_blocked() -> None:
    result = load_method_audit(AUDIT_JSON_PATH)
    assert can_run_biological_pipeline(result) is False
    assert can_promote_to_evidence_admissible(result) is False


# ---------------------------------------------------------------------------
# 14. Repo audit JSON contains no `generated_at` key
# ---------------------------------------------------------------------------


def test_14_audit_json_has_no_generated_at_key() -> None:
    raw = json.loads(AUDIT_JSON_PATH.read_text(encoding="utf-8"))

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            assert "generated_at" not in node, "audit JSON must not contain 'generated_at'"
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw)


# ---------------------------------------------------------------------------
# 15. Repo audit JSON contains no ISO-8601 timestamp pattern in any value
# ---------------------------------------------------------------------------


def test_15_audit_json_has_no_timestamp_pattern() -> None:
    contents = AUDIT_JSON_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
    assert pattern.search(contents) is None, (
        "audit JSON must not contain ISO-8601 timestamp patterns"
    )


# ---------------------------------------------------------------------------
# 16. validate_method_audit is deterministic — same input, same output
# ---------------------------------------------------------------------------


def test_16_validate_method_audit_is_deterministic() -> None:
    result_a = load_method_audit(AUDIT_JSON_PATH)
    result_b = load_method_audit(AUDIT_JSON_PATH)
    validation_a = validate_method_audit(result_a)
    validation_b = validate_method_audit(result_b)
    assert validation_a == validation_b
    assert validation_a.errors == validation_b.errors
    assert validation_a.warnings == validation_b.warnings


# ---------------------------------------------------------------------------
# 17. Audit document contains the `## Non-Claims` heading
# ---------------------------------------------------------------------------


def test_17_audit_doc_contains_non_claims_heading() -> None:
    text = AUDIT_DOC_PATH.read_text(encoding="utf-8")
    assert "## Non-Claims" in text


# ---------------------------------------------------------------------------
# 18. Audit document explicitly states "no fungal data"
# ---------------------------------------------------------------------------


def test_18_audit_doc_states_no_fungal_data() -> None:
    text = AUDIT_DOC_PATH.read_text(encoding="utf-8")
    # Must contain the verbatim non-claim line.
    assert "This audit does not analyze fungal data." in text


# ---------------------------------------------------------------------------
# Bonus: byte-stable JSON round-trip (deterministic file format)
# ---------------------------------------------------------------------------


def test_19_audit_json_is_byte_stable() -> None:
    """Defensive assertion that the on-disk JSON is exactly what
    `json.dump(..., sort_keys=True, indent=2)` would produce."""
    raw = AUDIT_JSON_PATH.read_text(encoding="utf-8")
    expected = json.dumps(json.loads(raw), sort_keys=True, indent=2) + "\n"
    assert raw == expected


# ---------------------------------------------------------------------------
# Bonus: ACCEPTED hypothetical with full data passes both gates
# ---------------------------------------------------------------------------


def test_20_accepted_hypothetical_passes_both_gates(tmp_path: Path) -> None:
    payload = _accepted_spectral_payload()
    # No DFA primary; DFA still appears in rejected list with h_tension explicit.
    payload["rejected_candidates"] = [
        {"candidate": "DFA_2H_PLUS_1", "reason": "DFA secondary only"},
    ]
    payload["h_tension_if_dfa"] = True
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    validation = validate_method_audit(result)
    assert validation.valid, f"unexpected errors: {validation.errors}"
    assert can_run_biological_pipeline(result) is True
    assert can_promote_to_evidence_admissible(result) is True


# ---------------------------------------------------------------------------
# Bonus: DFA primary with h_tension None blocks promotion even if ACCEPTED
# ---------------------------------------------------------------------------


def test_21_dfa_primary_without_h_tension_blocks_promotion(tmp_path: Path) -> None:
    payload = _accepted_spectral_payload()
    payload["primary_gamma_definition"] = "DFA_2H_PLUS_1"
    payload["primary_metric_name"] = "DFA Hurst exponent"
    payload["primary_metric_formula"] = "gamma = 2 H + 1"
    payload["h_tension_if_dfa"] = None
    payload["rejected_candidates"] = []
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    validation = validate_method_audit(result)
    assert not validation.valid
    assert can_promote_to_evidence_admissible(result) is False
    assert can_run_biological_pipeline(result) is False


# ---------------------------------------------------------------------------
# Bonus: secondary metrics never grant promotion in isolation
# ---------------------------------------------------------------------------


def test_22_secondary_metrics_alone_do_not_promote(tmp_path: Path) -> None:
    """Even when secondary metrics are richly populated, a BLOCKED status
    must keep both gates closed — secondary metrics never promote."""
    payload = deepcopy(_blocked_payload())
    payload["secondary_metrics"] = [
        "DFA alpha (per §2.3 secondary cross-check only)",
        "Branching ratio sigma (descriptive)",
        "Avalanche shape collapse (descriptive)",
    ]
    target = _write_payload(tmp_path, payload)
    result = load_method_audit(target)
    assert can_run_biological_pipeline(result) is False
    assert can_promote_to_evidence_admissible(result) is False
