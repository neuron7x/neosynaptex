"""Mycelium substrate — Method Gate 0 (definition audit only, no biological pipeline).

`SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY` is a γ-program **candidate** substrate.
This package ships the gate that enforces fail-closed semantics on the candidate:
no biological pipeline, no γ computation, and no evidence-admissible promotion
may run while the audit JSON reports `BLOCKED_BY_METHOD_DEFINITION`.
"""

from __future__ import annotations

from .method_gate import (
    MethodGateResult,
    MethodGateValidation,
    can_promote_to_evidence_admissible,
    can_run_biological_pipeline,
    load_method_audit,
    validate_method_audit,
)

__all__ = [
    "MethodGateResult",
    "MethodGateValidation",
    "can_promote_to_evidence_admissible",
    "can_run_biological_pipeline",
    "load_method_audit",
    "validate_method_audit",
]
