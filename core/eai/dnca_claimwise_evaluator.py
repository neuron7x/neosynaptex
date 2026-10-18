"""Held-out-style, paired claimwise ranking diagnostic; no DNCA efficacy claims.

Scoring uses committed per-claim cues and oracle labels only after selection.
A real oracle, source authentication, and full compute accounting are NOT supplied.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import TypedDict


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    group_id: str
    claim_id: str
    baseline: float
    signed_valence: float
    oracle_benefit_label: int
    oracle_receipt_sha256: str = ""


@dataclass(frozen=True, slots=True)
class StudyPlan:
    slots: int = 2
    gain: float = 0.25
    permutation_repeats: int = 199
    bootstrap_repeats: int = 499
    seed: int = 20261016


class TrialResult(TypedDict):
    group_id: str
    n_candidates: int
    n_selected: int
    baseline_benefit: int
    claimwise_benefit: int
    sign_reversed_benefit: int
    paired_delta: int
    cue_variation: float


def _finite(value: object, minimum: float, maximum: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}_not_numeric")
    x = float(value)
    if not math.isfinite(x) or not minimum <= x <= maximum:
        raise ValueError(f"{field}_invalid")
    return x


def _validate(rows: Sequence[ClaimEvidence], plan: StudyPlan) -> dict[str, list[ClaimEvidence]]:
    if not rows or len(rows) > 50000:
        raise ValueError("invalid_study_size")
    if type(plan.slots) is not int or plan.slots < 1:
        raise ValueError("invalid_slots")
    _finite(plan.gain, 0, 0.25, "gain")
    if (type(plan.permutation_repeats) is not int or not 19 <= plan.permutation_repeats <= 10000
            or type(plan.bootstrap_repeats) is not int or not 99 <= plan.bootstrap_repeats <= 10000
            or type(plan.seed) is not int):
        raise ValueError("invalid_resampling_plan")
    groups: dict[str, list[ClaimEvidence]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, ClaimEvidence):
            raise ValueError("invalid_record_type")
        if not (isinstance(row.group_id, str) and 0 < len(row.group_id) <= 128
                and isinstance(row.claim_id, str) and 0 < len(row.claim_id) <= 128):
            raise ValueError("invalid_identity")
        key = row.group_id, row.claim_id
        if key in seen:
            raise ValueError("duplicate_claim_identity")
        seen.add(key)
        _finite(row.baseline, 0, 1, "baseline")
        _finite(row.signed_valence, -1, 1, "signed_valence")
        if type(row.oracle_benefit_label) is not int or row.oracle_benefit_label not in (0, 1):
            raise ValueError("invalid_binary_outcome")
        if not isinstance(row.oracle_receipt_sha256, str) or (row.oracle_receipt_sha256 and (
                len(row.oracle_receipt_sha256) != 64
                or any(c not in "0123456789abcdef" for c in row.oracle_receipt_sha256))):
            raise ValueError("invalid_oracle_receipt_hash")
        groups.setdefault(row.group_id, []).append(row)
    if len(groups) < 4 or any(len(g) <= plan.slots for g in groups.values()):
        raise ValueError("insufficient_independent_groups_or_candidates")
    return dict(sorted(groups.items()))


def _score(group: list[ClaimEvidence], cues: Sequence[float], gain: float, slots: int) -> int:
    """Policy selection never touches hidden outcomes; oracle used only after top-k."""
    order = sorted(range(len(group)), key=lambda i: (
        -(group[i].baseline + gain * cues[i]), group[i].claim_id
    ))
    return sum(group[i].oracle_benefit_label for i in order[:slots])


def _paired_mean(values: Sequence[float]) -> float:
    return statistics.fmean(values)


def _paired_bootstrap(deltas: list[int], repeats: int, rng: random.Random) -> list[float]:
    n = len(deltas)
    draws = sorted(_paired_mean([deltas[rng.randrange(n)] for _ in range(n)])
                   for _ in range(repeats))
    return [draws[int((repeats - 1) * 0.025)], draws[int((repeats - 1) * 0.975)]]


def evaluate(rows: Sequence[ClaimEvidence], plan: StudyPlan | None = None) -> dict[str, object]:
    if plan is None:
        plan = StudyPlan()
    groups = _validate(rows, plan)
    rng = random.Random(plan.seed)
    trial_results: list[TrialResult] = []
    placebo: list[list[int]] = [[] for _ in range(plan.permutation_repeats)]
    for gid, group in groups.items():
        vals = [x.signed_valence for x in group]
        zeros = [0.0] * len(group)
        base = _score(group, zeros, plan.gain, plan.slots)
        chosen = _score(group, vals, plan.gain, plan.slots)
        inverted = _score(group, [-v for v in vals], plan.gain, plan.slots)
        for i in range(plan.permutation_repeats):
            shuffled = vals[:]
            rng.shuffle(shuffled)
            placebo[i].append(_score(group, shuffled, plan.gain, plan.slots) - base)
        trial_results.append({
            "group_id": gid,
            "n_candidates": len(group),
            "n_selected": plan.slots,
            "baseline_benefit": base,
            "claimwise_benefit": chosen,
            "sign_reversed_benefit": inverted,
            "paired_delta": chosen - base,
            "cue_variation": max(vals) - min(vals),
        })
    deltas = [z["paired_delta"] for z in trial_results]
    observed = _paired_mean(deltas)
    permutation_stats = [_paired_mean(sample) for sample in placebo]
    # +1 correction includes the observed statistic in the randomization ensemble.
    one_sided_p = (1 + sum(z >= observed - 1e-12 for z in permutation_stats)) / (
        plan.permutation_repeats + 1
    )
    ci = _paired_bootstrap(deltas, plan.bootstrap_repeats, rng)
    diversified = sum(z["cue_variation"] > 1e-12 for z in trial_results)
    input_raw = json.dumps(
        [asdict(r) for r in rows],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    result: dict[str, object] = {
        "protocol": "CLAIMWISE_PREQUENTIAL_DIAGNOSTIC_v1",
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "status": "UNQUALIFIED_ORACLE_AND_UNMETERED_COMPUTE",
        "scope": "DIAGNOSTIC_ASSOCIATION_NOT_CAUSAL_DNCA_BENEFIT",
        "plan": asdict(plan),
        "n_groups": len(groups),
        "n_cue_varying_groups": diversified,
        "groups": trial_results,
        "paired_gain_per_group": observed,
        "paired_bootstrap_95pct": ci,
        "within_group_permutation_p_one_sided": one_sided_p,
        "oracle_receipt_hashes_present": sum(bool(x.oracle_receipt_sha256) for x in rows),
        "oracle_receipt_hashes_verified": False,
        "end_to_end_cost_metered": False,
        "limitations": [
            "requires independent oracle attestation and audit of claim labels",
            "resampling assumes grouped trials are independent and within-group "
            "cue exchangeability",
            "positive association is not causal evidence of DNCA or model cognition",
            "same verification slots does not imply equal total computational cost",
            "no adaptive threshold fitting or selection on held-out outcomes permitted",
        ],
    }
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    result["sha256_pre_digest"] = hashlib.sha256(raw).hexdigest()
    return result
