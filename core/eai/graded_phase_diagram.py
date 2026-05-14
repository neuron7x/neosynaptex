"""Deterministic phase-diagram library for graded vs binary falsification.

CONTRACT (per docs/research/EAI_GRADED_FALSIFICATION_PHASE_DIAGRAM_V1.md):
    pre:  none — pure library, no external state.
    post: generate_grid() returns the exhaustive set of axis tuples;
          evaluate_cell(...) runs both gates deterministically and
          returns a per-cell record; classify_region(...) labels each
          cell into {useful, regression, null}; summarize_regions(...)
          aggregates per-class metrics.
    fail: never raises on valid axis inputs; degenerate combinations
          collapse to recorded null cells.
    inv:  the function set is pure (no time, no PRNG, no filesystem,
          no network). Two calls with identical args return identical
          values.

Production engine (``core.eai.engine``, ``core.iev_gate``,
``core.falsification_engine.falsification_decision``) is NEVER imported
in a mutating context here. The phase diagram is a DIAGNOSTIC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from core.eai.graded_gate import decide_with_graded_threshold
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)
from core.falsification_engine import (
    falsification_decision,
    falsification_decision_graded,
)

ClaimClass = Literal[
    "true_bounded",
    "false_obvious",
    "false_subtle",
    "ambiguous",
    "adversarial_authority",
    "adversarial_boundary_expansion",
    "adversarial_fake_citation",
    "adversarial_software_no_execution",
]
ContradictionDensity = Literal["none", "low", "medium", "high"]
RevalidationState = Literal["passed", "failed"]
BoundaryState = Literal["valid", "missing", "expanded", "contradictory"]

CONFLICT_MARKER_COUNT_RANGE: tuple[int, ...] = tuple(range(0, 9))  # 0..8
EVIDENCE_PATH_COUNT_RANGE: tuple[int, ...] = tuple(range(0, 9))  # 0..8
CLAIM_CLASSES: tuple[ClaimClass, ...] = (
    "true_bounded",
    "false_obvious",
    "false_subtle",
    "ambiguous",
    "adversarial_authority",
    "adversarial_boundary_expansion",
    "adversarial_fake_citation",
    "adversarial_software_no_execution",
)
CONTRADICTION_DENSITIES: tuple[ContradictionDensity, ...] = ("none", "low", "medium", "high")
REVALIDATION_STATES: tuple[RevalidationState, ...] = ("passed", "failed")
BOUNDARY_STATES: tuple[BoundaryState, ...] = ("valid", "missing", "expanded", "contradictory")


@dataclass(frozen=True)
class GridCell:
    """Axis tuple identifying one phase-diagram cell."""

    conflict_marker_count: int
    evidence_path_count: int
    claim_class: ClaimClass
    contradiction_density: ContradictionDensity
    revalidation_state: RevalidationState
    boundary_state: BoundaryState

    @property
    def cell_id(self) -> str:
        return (
            f"C-mc{self.conflict_marker_count}-ep{self.evidence_path_count}"
            f"-{self.claim_class}-{self.contradiction_density}"
            f"-{self.revalidation_state}-{self.boundary_state}"
        )


@dataclass(frozen=True)
class CellRecord:
    """Result of running both gates on a single grid cell."""

    cell_id: str
    axes: GridCell
    binary_verdict: str
    binary_reason: str
    graded_verdict: str
    graded_reason: str
    conflict_strength: float
    required_paths: int
    available_paths: int
    expected_status: str
    graded_reduced_false_promotion: bool
    graded_killed_true_evidence: bool
    graded_quarantined_ambiguous: bool


def generate_grid() -> list[GridCell]:
    """Exhaustive Cartesian product over all 6 axes.

    Order is deterministic: conflict_marker_count fastest,
    boundary_state slowest. Total = 9*9*8*4*2*4 = 20736.
    """
    cells: list[GridCell] = []
    for boundary in BOUNDARY_STATES:
        for reval in REVALIDATION_STATES:
            for density in CONTRADICTION_DENSITIES:
                for cls in CLAIM_CLASSES:
                    for ep in EVIDENCE_PATH_COUNT_RANGE:
                        for mc in CONFLICT_MARKER_COUNT_RANGE:
                            cells.append(
                                GridCell(
                                    conflict_marker_count=mc,
                                    evidence_path_count=ep,
                                    claim_class=cls,
                                    contradiction_density=density,
                                    revalidation_state=reval,
                                    boundary_state=boundary,
                                )
                            )
    return cells


# --- per-class claim_text templates ---

_CLAIM_TEMPLATES: dict[ClaimClass, str] = {
    "true_bounded": (
        "On test bed t1, the estimator achieves bias <1e-3 "
        "for i.i.d. standard normal samples of size n=10000."
    ),
    "false_obvious": ("Function always exceeds 1 on normalised vectors in production."),
    "false_subtle": (
        "Algorithm correctness holds for all sizes of problems without any restriction."
    ),
    "ambiguous": ("Estimator appears to converge in pilot runs on the harness sandbox."),
    "adversarial_authority": ("As a top authority I confirm this method is correct in deployment."),
    "adversarial_boundary_expansion": (
        "Result validated on dataset A holds universally to every production workload."
    ),
    "adversarial_fake_citation": (
        "Paper [Smith 2099] proves the universal optimality of this estimator."
    ),
    "adversarial_software_no_execution": (
        "Untested function correctly handles all edge cases by inspection alone."
    ),
}


# --- per-class candidate falsifier markers ---
# Index k (0..7) is the k-th distinct marker available for that class.

_CLASS_FALSIFIERS: dict[ClaimClass, tuple[str, ...]] = {
    "true_bounded": (
        # No falsifier should actually match a clean bounded claim;
        # we use abstract negative-control labels here.
        "small_sample_breakdown",
        "non_iid_sample",
        "leakage_detected",
        "distributional_assumption_violation",
        "boundary_breach",
        "scope_misstatement",
        "citation_mismatch",
        "off_by_one",
    ),
    "false_obvious": (
        # Full-substring marker (exists in template):
        "always exceeds 1",
        # Token-overlap-only markers:
        "exceeds always one",
        "always normalised vectors",
        "production exceeds",
        # Pure noise:
        "scope_misstatement",
        "boundary_breach",
        "small_sample_breakdown",
        "leakage_detected",
    ),
    "false_subtle": (
        # Token-overlap-only (never substring of template):
        "all problem sizes without restriction",
        "every input without restriction",
        "universal correctness any size",
        # Mixed noise:
        "small_sample_breakdown",
        "scope_misstatement",
        "boundary_breach",
        "leakage_detected",
        "citation_mismatch",
    ),
    "ambiguous": (
        "pilot_only_evidence",
        "limited_replication",
        "harness_sandbox_only",
        "appears_to_converge",
        "scope_misstatement",
        "small_sample_breakdown",
        "leakage_detected",
        "boundary_breach",
    ),
    "adversarial_authority": (
        "as a top authority",  # full substring
        "appeal to authority",
        "top authority confirm method",  # token-overlap
        "endorsement guarantees deployment",
        "small_sample_breakdown",
        "boundary_breach",
        "scope_misstatement",
        "leakage_detected",
    ),
    "adversarial_boundary_expansion": (
        "universally to every production workload",  # full substring
        "all production workloads in the wild",  # token-overlap
        "every dataset universal",
        "production workload universal",
        "scope_misstatement",
        "small_sample_breakdown",
        "boundary_breach",
        "leakage_detected",
    ),
    "adversarial_fake_citation": (
        "[smith 2099] proves",  # full substring (lowercase)
        "smith 2099 universal proves",  # token-overlap
        "paper proves universal optimality estimator",
        "citation proves universal",
        "scope_misstatement",
        "small_sample_breakdown",
        "boundary_breach",
        "citation_mismatch",
    ),
    "adversarial_software_no_execution": (
        "by inspection alone",  # full substring
        "alone inspection function untested",  # token-overlap
        "untested edge cases inspection",
        "handles edge cases untested",
        "small_sample_breakdown",
        "scope_misstatement",
        "boundary_breach",
        "leakage_detected",
    ),
}


def _markers_for_cell(cls: ClaimClass, n: int, density: ContradictionDensity) -> list[str]:
    """Return n markers; the first ``k`` are real (will match), rest are noise.

    Realisation count:
        none -> 0
        low  -> ceil(n/4)
        medium -> ceil(n/2)
        high -> n
    """
    if n <= 0:
        return []
    if density == "none":
        k = 0
    elif density == "low":
        k = math.ceil(n / 4)
    elif density == "medium":
        k = math.ceil(n / 2)
    else:  # high
        k = n
    pool_real = _CLASS_FALSIFIERS[cls][:4]  # first 4 entries are real-match
    pool_noise = _CLASS_FALSIFIERS[cls][4:]  # remaining 4 are noise
    out: list[str] = []
    for i in range(n):
        if i < k:
            out.append(pool_real[i % len(pool_real)])
        else:
            out.append(pool_noise[i % len(pool_noise)])
    return out


def _boundary_for_state(state: BoundaryState, substrate: str = "bench_t1") -> BoundaryCard:
    if state == "valid":
        return BoundaryCard(
            boundary_id="BND-valid",
            valid_for=[substrate],
            invalid_for=["unrelated_substrate"],
            tested_conditions=[substrate],
            untested_conditions=["other"],
        )
    if state == "missing":
        return BoundaryCard(
            boundary_id="BND-missing",
            valid_for=[],
            invalid_for=["unrelated_substrate"],
            tested_conditions=[],
            untested_conditions=["other"],
        )
    if state == "expanded":
        return BoundaryCard(
            boundary_id="BND-expanded",
            valid_for=[substrate, "global", "universal"],
            invalid_for=[],
            tested_conditions=[substrate],
            untested_conditions=["other"],
        )
    # contradictory
    return BoundaryCard(
        boundary_id="BND-contradictory",
        valid_for=[substrate, "in_conflict"],
        invalid_for=["in_conflict"],
        tested_conditions=[substrate],
        untested_conditions=["other"],
    )


def _expected_status_for_class(cls: ClaimClass) -> str:
    """Authoritative expected verdict per class, independent of cell axes.

    Note: a cell's *actual* verdict depends on additional axes
    (boundary_state, revalidation_state, marker realisation). This is
    the per-class *baseline expectation* used for FP/FK/TP labelling.
    """
    if cls == "true_bounded":
        return "EVIDENCE"
    if cls == "ambiguous":
        return "QUARANTINED"
    return "KILLED"  # false_*, adversarial_*


def evaluate_cell(cell: GridCell) -> CellRecord:
    """Run binary + graded gates on the synthesised triplet for ``cell``."""
    claim_text = _CLAIM_TEMPLATES[cell.claim_class]
    markers = _markers_for_cell(
        cell.claim_class, cell.conflict_marker_count, cell.contradiction_density
    )
    boundary = _boundary_for_state(cell.boundary_state)
    artifact = EvidenceArtifact(
        artifact_id=f"EVD-{cell.cell_id}",
        claim=ClaimCard(
            claim_id=f"CLM-{cell.cell_id}",
            claim_text=claim_text,
            claim_type=ClaimType.FACTUAL,
        ),
        boundary=boundary,
        falsification_report=FalsificationReport(["gate_falsification"], True),
        reproducibility=ReproducibilityManifest(
            commands=["pytest"], environment="phase-diagram-v1", artifact_hash="a" * 64
        ),
        integration_permission=True,
        revalidation_evidence_paths=[f"p{i}" for i in range(cell.evidence_path_count)],
    )

    # Binary gate (substring-only falsification + classic IEV semantics
    # via graded_gate with conflict_strength=0.0).
    binary_passed, binary_reason = falsification_decision(claim_text, markers)
    if not binary_passed:
        binary_verdict = "KILLED"
    else:
        bin_decision = decide_with_graded_threshold(
            artifact,
            retention_hash="a" * 64,
            revalidation_passed=(cell.revalidation_state == "passed"),
            conflict_strength=0.0,
        )
        binary_verdict = bin_decision.status
        binary_reason = bin_decision.reason

    # Graded gate (token-overlap falsifier + threshold-modulated IEV).
    gr = falsification_decision_graded(claim_text, markers)
    if not gr.passed:
        graded_verdict = "KILLED"
        graded_reason = gr.reason
        graded_required = 0
        graded_available = cell.evidence_path_count
    else:
        gr_decision = decide_with_graded_threshold(
            artifact,
            retention_hash="a" * 64,
            revalidation_passed=(cell.revalidation_state == "passed"),
            conflict_strength=gr.conflict_strength,
        )
        graded_verdict = gr_decision.status
        graded_reason = gr_decision.reason
        graded_required = gr_decision.required_paths
        graded_available = gr_decision.available_paths

    expected = _expected_status_for_class(cell.claim_class)
    graded_reduced_fp = (
        expected != "EVIDENCE" and binary_verdict == "EVIDENCE" and graded_verdict != "EVIDENCE"
    )
    # Codex P1.1 fix: `graded_killed_true_evidence` must measure
    # graded-SPECIFIC regression, i.e. graded kills a true-bounded
    # cell that binary would have left alive. When binary also kills
    # (e.g. boundary_state=missing makes can_be_promoted False for
    # BOTH gates), graded did not cause regression — it concurred
    # with binary on a structurally invalid cell.
    graded_killed_te = (
        expected == "EVIDENCE" and graded_verdict == "KILLED" and binary_verdict != "KILLED"
    )
    graded_quar_amb = (
        expected == "QUARANTINED"
        and binary_verdict != "QUARANTINED"
        and graded_verdict == "QUARANTINED"
    )

    return CellRecord(
        cell_id=cell.cell_id,
        axes=cell,
        binary_verdict=binary_verdict,
        binary_reason=binary_reason,
        graded_verdict=graded_verdict,
        graded_reason=graded_reason,
        conflict_strength=gr.conflict_strength,
        required_paths=graded_required,
        available_paths=graded_available,
        expected_status=expected,
        graded_reduced_false_promotion=graded_reduced_fp,
        graded_killed_true_evidence=graded_killed_te,
        graded_quarantined_ambiguous=graded_quar_amb,
    )


def classify_region(record: CellRecord) -> str:
    """Label a single cell as one of {useful, regression, null}."""
    if record.graded_killed_true_evidence:
        return "regression"
    if record.graded_reduced_false_promotion:
        return "useful"
    if record.graded_quarantined_ambiguous:
        return "useful"
    return "null"


def _per_class_metrics(records: list[CellRecord], cls: ClaimClass) -> dict[str, Any]:
    """Aggregate per-class metrics over all cells of that class."""
    class_records = [r for r in records if r.axes.claim_class == cls]
    n = len(class_records)
    expected = _expected_status_for_class(cls)
    evidence_total = sum(1 for r in class_records if r.expected_status == "EVIDENCE")
    non_evidence_total = n - evidence_total

    binary_fp = sum(
        1
        for r in class_records
        if r.expected_status != "EVIDENCE" and r.binary_verdict == "EVIDENCE"
    )
    graded_fp = sum(
        1
        for r in class_records
        if r.expected_status != "EVIDENCE" and r.graded_verdict == "EVIDENCE"
    )
    binary_tp = sum(
        1
        for r in class_records
        if r.expected_status == "EVIDENCE" and r.binary_verdict == "EVIDENCE"
    )
    graded_tp = sum(
        1
        for r in class_records
        if r.expected_status == "EVIDENCE" and r.graded_verdict == "EVIDENCE"
    )
    binary_quar = sum(1 for r in class_records if r.binary_verdict == "QUARANTINED")
    graded_quar = sum(1 for r in class_records if r.graded_verdict == "QUARANTINED")

    binary_fpr = binary_fp / non_evidence_total if non_evidence_total else 0.0
    graded_fpr = graded_fp / non_evidence_total if non_evidence_total else 0.0
    binary_tpr = binary_tp / evidence_total if evidence_total else 0.0
    graded_tpr = graded_tp / evidence_total if evidence_total else 0.0

    regression_cells = sum(1 for r in class_records if r.graded_killed_true_evidence)
    useful_cells = sum(1 for r in class_records if classify_region(r) == "useful")
    null_cells = sum(1 for r in class_records if classify_region(r) == "null")

    return {
        "claim_class": cls,
        "expected_status": expected,
        "total_cells": n,
        "binary_false_promotion_rate": round(binary_fpr, 6),
        "graded_false_promotion_rate": round(graded_fpr, 6),
        "binary_true_positive_rate": round(binary_tpr, 6),
        "graded_true_positive_rate": round(graded_tpr, 6),
        "graded_delta_false_promotion": round(graded_fpr - binary_fpr, 6),
        "graded_delta_true_positive": round(graded_tpr - binary_tpr, 6),
        "quarantine_delta": graded_quar - binary_quar,
        "regression_cells_count": regression_cells,
        "useful_cells_count": useful_cells,
        "null_cells_count": null_cells,
    }


def _zone_key(r: CellRecord) -> tuple[BoundaryState, RevalidationState]:
    """Per-pre-registration: a 'zone' is the (boundary_state,
    revalidation_state) tuple. The PHASE_REGION_FOUND rule requires
    co-occurrence within the SAME zone, not globally."""
    return (r.axes.boundary_state, r.axes.revalidation_state)


def summarize_regions(records: list[CellRecord]) -> dict[str, Any]:
    """Aggregate global + per-class summary; apply pre-registered
    ZONE-LEVEL verdict rules (Codex P1.2 fix).

    The pre-registration in
    docs/research/EAI_GRADED_FALSIFICATION_PHASE_DIAGRAM_V1.md
    requires verdict aggregation by (boundary_state, revalidation_state)
    zone, not by global counts. This implementation walks the 8 zones
    and applies the rule:

      - In each zone, count (useful, regression_true_bounded).
      - If ANY zone has useful>0 AND regression_true_bounded==0:
          a separable region exists -> PHASE_REGION_FOUND
          (provided no OTHER target class regresses globally).
      - Else if ANY zone has useful>0 AND regression>0 in the same zone:
          regression dominates -> REGRESSION_REGION_FOUND
      - Else if NO zone has useful>0:
          no separable region -> NO_SEPARABLE_REGION_FOUND
    """

    per_class = {cls: _per_class_metrics(records, cls) for cls in CLAIM_CLASSES}
    total_cells = len(records)
    regression_cells_global = sum(1 for r in records if r.graded_killed_true_evidence)
    useful_cells_global = sum(1 for r in records if classify_region(r) == "useful")
    null_cells_global = sum(1 for r in records if classify_region(r) == "null")
    regression_cells_in_true_bounded = per_class["true_bounded"]["regression_cells_count"]

    # --- Zone-level aggregation (Codex P1.2) ---
    zones: dict[tuple[BoundaryState, RevalidationState], dict[str, int]] = {}
    for boundary in BOUNDARY_STATES:
        for reval in REVALIDATION_STATES:
            zones[(boundary, reval)] = {"useful": 0, "regression": 0}
    for r in records:
        zk = _zone_key(r)
        region = classify_region(r)
        if region == "useful":
            zones[zk]["useful"] += 1
        if r.graded_killed_true_evidence:
            zones[zk]["regression"] += 1

    zone_separable: list[tuple[BoundaryState, RevalidationState]] = []
    zone_regression: list[tuple[BoundaryState, RevalidationState]] = []
    for zk, counts in zones.items():
        if counts["useful"] > 0 and counts["regression"] == 0:
            zone_separable.append(zk)
        elif counts["useful"] > 0 and counts["regression"] > 0:
            zone_regression.append(zk)

    # PHASE_REGION_FOUND: at least one zone is cleanly separable
    # (useful gains AND zero true-bounded regression in that zone).
    if zone_separable:
        verdict = "PHASE_REGION_FOUND"
        verdict_reason = (
            f"separable zones (useful>0 AND regression==0): "
            f"{[f'{b}/{r}' for (b, r) in zone_separable]}; "
            f"co-regression zones: {[f'{b}/{r}' for (b, r) in zone_regression]}"
        )
    elif zone_regression:
        # All useful zones are co-located with regression -> graded
        # only helps by killing true evidence.
        verdict = "REGRESSION_REGION_FOUND"
        verdict_reason = (
            f"useful gains exist ONLY in zones that also regress "
            f"true-bounded evidence: {[f'{b}/{r}' for (b, r) in zone_regression]}; "
            "no separable zone."
        )
    elif useful_cells_global == 0 and regression_cells_in_true_bounded == 0:
        verdict = "NO_SEPARABLE_REGION_FOUND"
        verdict_reason = (
            "graded did not improve in any zone and did not regress "
            "true-bounded evidence; graded == binary across the grid."
        )
    else:
        # Edge case: regression exists but no useful gains anywhere.
        verdict = "REGRESSION_REGION_FOUND"
        verdict_reason = (
            f"regression_cells_in_true_bounded={regression_cells_in_true_bounded} > 0 "
            f"with useful_cells_global={useful_cells_global}; "
            "graded reduces nothing and kills real evidence."
        )

    zone_breakdown = {
        f"{b}/{r}": {"useful": c["useful"], "regression": c["regression"]}
        for (b, r), c in zones.items()
    }

    return {
        "total_cells": total_cells,
        "useful_cells_global": useful_cells_global,
        "regression_cells_global": regression_cells_global,
        "null_cells_global": null_cells_global,
        "regression_cells_in_true_bounded": regression_cells_in_true_bounded,
        "zone_breakdown": zone_breakdown,
        "zone_separable": [f"{b}/{r}" for (b, r) in zone_separable],
        "zone_regression": [f"{b}/{r}" for (b, r) in zone_regression],
        "per_class": per_class,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


def compute_region_metrics(records: list[CellRecord]) -> dict[str, int]:
    """Top-level region counts (kept separate for CLI consumption)."""
    region_counts: dict[str, int] = {"useful": 0, "regression": 0, "null": 0}
    for r in records:
        region_counts[classify_region(r)] += 1
    return region_counts
