"""Pure mathematics for global-vs-claimwise DNCA routing identifiability.

No neural result, causal claim, or verifier quality is inferred here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence


def _finite(name: str, v: float, *, lower: float, upper: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (float, int)):
        raise ValueError(f"{name}_not_numeric")
    result = float(v)
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError(f"{name}_outside_bounds_or_nonfinite")
    return result


def validate_scores(bases: Sequence[float], cues: Sequence[float], gain: float) -> tuple[tuple[float,...], tuple[float,...], float]:
    if len(bases) < 2 or len(bases) != len(cues):
        raise ValueError("at_least_two_equal_length_vectors_required")
    g = _finite("gain", gain, lower=0, upper=0.25)
    b = tuple(_finite("base", v, lower=0, upper=1e12) for v in bases)
    c = tuple(_finite("cue", v, lower=-1, upper=1) for v in cues)
    return b,c,g


def priorities(bases: Sequence[float], cues: Sequence[float], gain: float) -> tuple[float,...]:
    b,c,g = validate_scores(bases, cues, gain)
    return tuple(max(0.0, base + g*cue) for base,cue in zip(b,c))


def strict_inversions(before: Sequence[float], after: Sequence[float]) -> int:
    """Strict pairwise inversions; ties do not count, but may change top-k.

    This is only valid when comparing identical claim identities/order.
    """
    if len(before) != len(after):
        raise ValueError("dimension_mismatch")
    total=0
    for i in range(len(before)):
        for j in range(i+1,len(before)):
            a = before[i]-before[j]
            b = after[i]-after[j]
            if (a > 0 and b < 0) or (a < 0 and b > 0):
                total+=1
    return total


@dataclass(frozen=True)
class GlobalShiftAudit:
    scope: str
    strict_inversions: int
    clipping_ties: int
    explanation: str


def audit_global_shift(bases: Sequence[float], common_valence: float, gain: float) -> GlobalShiftAudit:
    v = _finite("common_valence", common_valence,lower=-1,upper=1)
    b = tuple(bases)
    modified = priorities(b, [v]*len(b), gain)
    inversions = strict_inversions(b,modified)
    clipping_ties = sum(b[i]!=b[j] and modified[i]==modified[j]
        for i in range(len(b)) for j in range(i+1,len(b)))
    if inversions != 0:
        raise AssertionError("order_preservation_invariant_violated")
    return GlobalShiftAudit(
        "GLOBAL_THRESHOLD_SHIFT_NOT_CLAIM_SPECIFIC",
        inversions, clipping_ties,
        "Shared signed shift cannot strictly reverse order at fixed base scores; thresholds and sequential budgets may still change routing.",
    )


def select_claims(scores: Sequence[float], slots: int) -> tuple[int,...]:
    if isinstance(slots,bool) or not isinstance(slots,int) or not 0 < slots < len(scores):
        raise ValueError("invalid_slots")
    validated = [_finite("score",v,lower=0,upper=1e12) for v in scores]
    return tuple(sorted(range(len(validated)),key=lambda i: (-validated[i], i))[:slots])


def score_selected(selection: Sequence[int], withheld_utility: Sequence[int]) -> int:
    if len(set(selection)) != len(selection) or any(i<0 or i>=len(withheld_utility) for i in selection):
        raise ValueError("invalid_selected_indices")
    if any(type(v) is not int or v not in (0,1) for v in withheld_utility):
        raise ValueError("utility_must_be_binary_and_independent")
    return sum(withheld_utility[i] for i in selection)


def paired_claimwise_probe(bases: Sequence[float], cues: Sequence[float],
                           withheld_utility: Sequence[int], slots: int, seed: int=731) -> dict[str,object]:
    """Diagnostics, NOT DNCA validation. Labels used after selection only."""
    b,c,_ = validate_scores(bases,cues,0.25)
    if len(withheld_utility)!=len(b):
        raise ValueError("utility_length_mismatch")
    shuffle = list(c)
    random.Random(seed).shuffle(shuffle)
    scores = {
        "baseline": b,
        "claim_specific": priorities(b,c,0.25),
        "permuted": priorities(b,shuffle,0.25),
        "sign_reversed": priorities(b,[-x for x in c],0.25),
        "global_mean_shift": priorities(b,[sum(c)/len(c)]*len(c),0.25),
    }
    selections = {name: select_claims(v,slots) for name,v in scores.items()}
    utility = {name:score_selected(sel,withheld_utility) for name,sel in selections.items()}
    return {
        "scope":"DIAGNOSTIC_ONLY_NOT_SIGNAL_QUALIFICATION",
        "cue_diversity":max(c)-min(c),
        "claim_specific_strict_inversions":strict_inversions(b,scores["claim_specific"]),
        "global_shift_strict_inversions":strict_inversions(b,scores["global_mean_shift"]),
        "selection":selections,
        "utility":utility,
        "all_arms_same_slots":all(len(v)==slots for v in selections.values()),
        "cost_status":"DNCA_INFERENCE_NOT_METERED",
    }
