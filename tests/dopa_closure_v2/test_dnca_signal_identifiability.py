import math
import random

import pytest

from core.eai.dnca_signal_identifiability import (
    audit_global_shift,
    paired_claimwise_probe,
    priorities,
    score_selected,
    strict_inversions,
)


def test_common_global_shift_never_inverts_5000_examples():
    rng = random.Random(8)
    for _ in range(5000):
        xs = [rng.random() for _ in range(8)]
        v = rng.uniform(-1, 1)
        g = rng.uniform(0, 0.25)
        a = audit_global_shift(xs, v, g)
        assert a.strict_inversions == 0


def test_negative_shift_can_create_ties_not_reversals():
    a = audit_global_shift([0.01, 0.02, 0.3], -1, 0.25)
    assert a.clipping_ties == 1 and a.strict_inversions == 0


def test_claim_specific_can_invert():
    before = [0.5, 0.6, 0.7]
    after = priorities(before, [1, 0, -1], 0.25)
    assert strict_inversions(before, after) > 0


def test_constant_claimwise_cue_is_global_and_no_inversion():
    b = [0.2, 0.4, 0.6, 0.8]
    assert strict_inversions(b, priorities(b, [0.5] * 4, 0.25)) == 0


def test_zero_gain_identity():
    b = [0.1, 0.4, 0.9]
    assert priorities(b, [-1, 1, 1], 0) == tuple(b)


def test_claimwise_withheld_label_does_not_change_selection():
    b = [0.5, 0.6, 0.7, 0.8]
    c = [1, -1, 1, -1]
    r1 = paired_claimwise_probe(b, c, [0, 1, 0, 1], 2)
    r2 = paired_claimwise_probe(b, c, [1, 0, 1, 0], 2)
    assert r1["selection"] == r2["selection"]


def test_global_rank_reported_nondiscriminative():
    out = paired_claimwise_probe([0.1, 0.3, 0.5, 0.7], [-1, 1, -1, 1], [0, 1, 0, 1], 2)
    assert out["global_shift_strict_inversions"] == 0
    assert out["cost_status"] == "DNCA_INFERENCE_NOT_METERED"
    assert out["all_arms_same_slots"]


@pytest.mark.parametrize(
    "xs,c,g",
    [
        ([1, 2], [0, 1], math.nan),
        ([1, 2], [0, 1], 0.26),
        ([1, 2], [0, math.nan], 0.1),
        ([1, -2], [0, 1], 0.1),
        ([1], [0], 0.1),
        ([1, 2], [0], 0.1),
    ],
)
def test_bad_inputs_fail_closed(xs, c, g):
    with pytest.raises(ValueError):
        priorities(xs, c, g)


def test_invalid_utilities_fail_closed():
    with pytest.raises(ValueError):
        score_selected((1, 1), [0, 1, 0])
    with pytest.raises(ValueError):
        score_selected((0,), [0, 1.1, 0])
