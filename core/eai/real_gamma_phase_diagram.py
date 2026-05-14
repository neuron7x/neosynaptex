"""Real-data phase-diagram library: binary vs graded gate on the
γ-ledger.

CONTRACT (per docs/research/EAI_REAL_GAMMA_PHASE_DIAGRAM_V1.md):
    pre:  path to γ-ledger JSON (read-only); no external state mutation.
    post: generate_grid() returns 490 axis tuples; evaluate_cell(...)
          runs both gates deterministically on a cell built from REAL
          ledger description text; classify_region(...) labels each
          cell into {useful, regression, null}; summarize_regions(...)
          aggregates per-zone metrics + applies pre-registered verdict.
    fail: never raises on a well-formed ledger; degenerate cases
          collapse to recorded null cells.
    inv:  the function set is pure (no time, no PRNG, no filesystem
          writes, no network). γ-ledger is read-only.

Production engine modules are NEVER imported in a mutating context.
This library composes PR #193's gamma_bridge (also read-only over
the ledger) plus PR #196's graded_gate; both are unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from core.eai.gamma_bridge import (
    GammaGateInputs,
    ledger_entry_to_gate_inputs,
)
from core.eai.graded_gate import decide_with_graded_threshold
from core.eai.intelligence_cycle import EvidenceArtifact, FalsificationReport
from core.falsification_engine import (
    falsification_decision,
    falsification_decision_graded,
)

# Fixed canonical probe pool — identical for every cell. No per-entry
# tuning permitted by pre-registration.
PROBES: tuple[str, ...] = (
    "universal scaling validated cross substrate",
    "all substrates demonstrate gamma convergence",
    "production ready scaling law every substrate",
    "every measured substrate converges to one",
    "scientific PASS substrate cohort universal",
    "validated universal gamma across all benchmarks",
)
PROBE_COUNT_RANGE: tuple[int, ...] = tuple(range(0, 7))  # 0..6
EVIDENCE_PATH_COUNT_RANGE: tuple[int, ...] = tuple(range(0, 7))  # 0..6

# Region label: deterministic from per-cell flags.
Region = Literal["useful", "regression", "null"]


@dataclass(frozen=True)
class RealGridCell:
    """Axis tuple identifying one real-data phase-diagram cell."""

    ledger_key: str
    probe_count_used: int
    evidence_path_count: int

    @property
    def cell_id(self) -> str:
        return f"C-{self.ledger_key}-pc{self.probe_count_used}-ep{self.evidence_path_count}"


@dataclass(frozen=True)
class RealCellRecord:
    """Result of running both gates on one real-data cell."""

    cell_id: str
    axes: RealGridCell
    ledger_substrate: str
    ledger_status: str
    ledger_evidence_tier: str
    hash_bound: bool
    binary_verdict: str
    binary_reason: str
    graded_verdict: str
    graded_reason: str
    conflict_strength: float
    required_paths: int
    available_paths: int
    useful: bool
    regression: bool
    null_cell: bool


def generate_grid(entry_keys: list[str]) -> list[RealGridCell]:
    """Exhaustive product over ledger_key × probe_count × evidence_path_count.

    ``entry_keys`` must be the SORTED list of γ-ledger entry keys
    (deterministic order). 10 entries × 7 × 7 = 490 cells.
    """
    cells: list[RealGridCell] = []
    for key in sorted(entry_keys):
        for ep in EVIDENCE_PATH_COUNT_RANGE:
            for pc in PROBE_COUNT_RANGE:
                cells.append(
                    RealGridCell(
                        ledger_key=key,
                        probe_count_used=pc,
                        evidence_path_count=ep,
                    )
                )
    return cells


def _replace_evidence_paths(art: EvidenceArtifact, n: int) -> EvidenceArtifact:
    """Return a copy of ``art`` with ``revalidation_evidence_paths``
    of length ``n``. EvidenceArtifact is a dataclass (not frozen) so
    we rebuild for clarity rather than mutate in place."""
    return EvidenceArtifact(
        artifact_id=art.artifact_id,
        claim=art.claim,
        boundary=art.boundary,
        falsification_report=art.falsification_report,
        reproducibility=art.reproducibility,
        integration_permission=art.integration_permission,
        revalidation_evidence_paths=[f"p{i}" for i in range(n)],
    )


def _is_hash_bound(gi: GammaGateInputs) -> bool:
    return bool(gi.hash_bound)


def _expected_evidence_for_cell(entry: dict[str, Any], gi: GammaGateInputs) -> bool:
    """An entry counts as 'hash-bound EVIDENCE_CANDIDATE' iff
    ledger_status == EVIDENCE_CANDIDATE AND data_sha256 is real.
    These are the entries on which a graded KILL counts as
    regression."""
    return str(entry.get("status") or "") == "EVIDENCE_CANDIDATE" and gi.hash_bound


def evaluate_cell(
    cell: RealGridCell,
    entry: dict[str, Any],
    ledger_version: str,
) -> RealCellRecord:
    """Run binary + graded gates on a real-ledger-derived input
    augmented with ``cell.probe_count_used`` canonical probes and
    ``cell.evidence_path_count`` synthetic revalidation paths."""
    gi = ledger_entry_to_gate_inputs(cell.ledger_key, entry, ledger_version=ledger_version)
    # Augment markers with first N probes (no per-entry tuning).
    probe_markers = list(PROBES[: cell.probe_count_used])
    combined_markers = list(gi.contradiction_markers) + probe_markers
    # Replace falsification_report with a structurally-valid one
    # (the engine's internal synthesis), so can_be_promoted's
    # structural check is satisfied.
    artifact_in = EvidenceArtifact(
        artifact_id=gi.claim.claim_id.replace("CLM-", "EVD-")
        if gi.claim.claim_id.startswith("CLM-")
        else f"EVD-{gi.claim.claim_id}",
        claim=gi.claim,
        boundary=gi.boundary,
        falsification_report=FalsificationReport(["gate_falsification"], True),
        reproducibility=gi.reproducibility,
        integration_permission=True,
        revalidation_evidence_paths=[],
    )
    artifact = _replace_evidence_paths(artifact_in, cell.evidence_path_count)

    claim_text = gi.claim.claim_text

    # Binary gate
    binary_passed, binary_reason = falsification_decision(claim_text, combined_markers)
    if not binary_passed:
        binary_verdict = "KILLED"
    else:
        bd = decide_with_graded_threshold(
            artifact,
            retention_hash=gi.retention_hash,
            revalidation_passed=gi.revalidation_passed,
            conflict_strength=0.0,
        )
        binary_verdict = bd.status
        binary_reason = bd.reason

    # Graded gate
    gr = falsification_decision_graded(claim_text, combined_markers)
    if not gr.passed:
        graded_verdict = "KILLED"
        graded_reason = gr.reason
        graded_required = 0
        graded_available = cell.evidence_path_count
    else:
        gd = decide_with_graded_threshold(
            artifact,
            retention_hash=gi.retention_hash,
            revalidation_passed=gi.revalidation_passed,
            conflict_strength=gr.conflict_strength,
        )
        graded_verdict = gd.status
        graded_reason = gd.reason
        graded_required = gd.required_paths
        graded_available = gd.available_paths

    # Region labelling (per pre-registration):
    #   useful     = graded more conservative AND verdicts differ
    #   regression = graded KILLED a hash-bound EVIDENCE_CANDIDATE that
    #                binary promoted to EVIDENCE
    #   null       = verdicts identical
    is_hash_bound_evidence = _expected_evidence_for_cell(entry, gi)
    regression = (
        is_hash_bound_evidence and graded_verdict == "KILLED" and binary_verdict == "EVIDENCE"
    )
    # "More conservative" ordering: EVIDENCE > QUARANTINED > KILLED in
    # terms of openness; we use a verdict rank for clarity.
    _rank = {"EVIDENCE": 2, "QUARANTINED": 1, "KILLED": 0}
    useful = (
        not regression
        and binary_verdict != graded_verdict
        and _rank[graded_verdict] < _rank[binary_verdict]
    )
    null_cell = binary_verdict == graded_verdict

    return RealCellRecord(
        cell_id=cell.cell_id,
        axes=cell,
        ledger_substrate=str(entry.get("substrate") or ""),
        ledger_status=str(entry.get("status") or ""),
        ledger_evidence_tier=str(entry.get("evidence_tier") or ""),
        hash_bound=_is_hash_bound(gi),
        binary_verdict=binary_verdict,
        binary_reason=binary_reason,
        graded_verdict=graded_verdict,
        graded_reason=graded_reason,
        conflict_strength=gr.conflict_strength,
        required_paths=graded_required,
        available_paths=graded_available,
        useful=useful,
        regression=regression,
        null_cell=null_cell,
    )


def classify_region(r: RealCellRecord) -> Region:
    if r.regression:
        return "regression"
    if r.useful:
        return "useful"
    return "null"


def _zone_key(r: RealCellRecord) -> tuple[str, str]:
    """Zone = (ledger_evidence_tier, ledger_status). Pre-registered."""
    return (r.ledger_evidence_tier, r.ledger_status)


def summarize_regions(records: list[RealCellRecord]) -> dict[str, Any]:
    """Aggregate per-zone counts and apply pre-registered verdict
    rules. Identical structure to PR #196."""

    total_cells = len(records)
    useful_global = sum(1 for r in records if r.useful)
    regression_global = sum(1 for r in records if r.regression)
    null_global = sum(1 for r in records if r.null_cell)

    zones: dict[tuple[str, str], dict[str, int]] = {}
    for r in records:
        zk = _zone_key(r)
        zone = zones.setdefault(zk, {"useful": 0, "regression": 0, "null": 0})
        if r.useful:
            zone["useful"] += 1
        if r.regression:
            zone["regression"] += 1
        if r.null_cell:
            zone["null"] += 1

    zone_separable: list[tuple[str, str]] = []
    zone_regression: list[tuple[str, str]] = []
    for zk, counts in zones.items():
        if counts["useful"] > 0 and counts["regression"] == 0:
            zone_separable.append(zk)
        elif counts["useful"] > 0 and counts["regression"] > 0:
            zone_regression.append(zk)

    if zone_separable:
        verdict = "PHASE_REGION_FOUND"
        verdict_reason = (
            f"separable zones (useful>0 AND regression==0): "
            f"{[f'{t}/{s}' for (t, s) in zone_separable]}; "
            f"co-regression zones: {[f'{t}/{s}' for (t, s) in zone_regression]}"
        )
    elif zone_regression:
        verdict = "REGRESSION_REGION_FOUND"
        verdict_reason = (
            f"useful gains exist ONLY in zones that also regress "
            f"hash-bound EVIDENCE_CANDIDATE entries: "
            f"{[f'{t}/{s}' for (t, s) in zone_regression]}"
        )
    elif useful_global == 0 and regression_global == 0:
        verdict = "NO_SEPARABLE_REGION_FOUND"
        verdict_reason = (
            "graded gate produces identical verdicts to binary on every "
            "real-ledger cell across the probe-count and evidence-path "
            "sweeps; STN-analog is a grid artifact of PR #196 synthetic "
            "templates."
        )
    else:
        verdict = "REGRESSION_REGION_FOUND"
        verdict_reason = (
            f"regression_global={regression_global} > 0 with "
            f"useful_global={useful_global}; graded harms real evidence."
        )

    zone_breakdown = {f"{t}/{s}": counts for (t, s), counts in sorted(zones.items())}
    return {
        "total_cells": total_cells,
        "useful_global": useful_global,
        "regression_global": regression_global,
        "null_global": null_global,
        "zone_breakdown": zone_breakdown,
        "zone_separable": [f"{t}/{s}" for (t, s) in zone_separable],
        "zone_regression": [f"{t}/{s}" for (t, s) in zone_regression],
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }
