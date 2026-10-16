from dataclasses import replace
import pytest
from core.eai.dnca_claimwise_evaluator import ClaimEvidence, StudyPlan, evaluate, _score


def synthetic(informative=True, groups=16):
    rows=[]
    for g in range(groups):
        for i in range(12):
            benefit=int(i>=8)
            cue=(0.8 if benefit else -0.8) if informative else 0.0
            rows.append(ClaimEvidence(str(g),str(i),0.5,cue,benefit))
    return rows


def test_deterministic_digest_and_statistics():
    a=evaluate(synthetic(),StudyPlan())
    b=evaluate(synthetic(),StudyPlan())
    assert a==b
    assert len(a['sha256_pre_digest'])==64


def test_positive_control_has_signal_and_negative_direction():
    out=evaluate(synthetic())
    assert out['paired_gain_per_group']>0
    assert out['within_group_permutation_p_one_sided']<=0.05
    assert out['n_cue_varying_groups']==16
    assert out['status']=='UNQUALIFIED_ORACLE_AND_UNMETERED_COMPUTE'


def test_constant_cue_is_identical_to_baseline():
    out=evaluate(synthetic(informative=False))
    assert out['paired_gain_per_group']==0
    assert out['n_cue_varying_groups']==0
    assert out['within_group_permutation_p_one_sided']==1


def test_hidden_label_flip_does_not_change_policy_selection():
    rows=synthetic()
    group=rows[:12]
    cues=[x.signed_valence for x in group]
    inverted=[replace(x,oracle_benefit_label=1-x.oracle_benefit_label) for x in group]
    def select(xs):
        return tuple(sorted(range(len(xs)),key=lambda i:(-(xs[i].baseline+0.25*cues[i]),xs[i].claim_id))[:2])
    assert select(group)==select(inverted)
    assert _score(group,cues,0.25,2)!=_score(inverted,cues,0.25,2)


def test_invalid_outcomes_rejected():
    rows=synthetic()
    rows[0]=replace(rows[0],oracle_benefit_label=2)
    with pytest.raises(ValueError,match='invalid_binary_outcome'):
        evaluate(rows)


def test_duplicate_group_id_claim_id_rejected():
    rows=synthetic()
    with pytest.raises(ValueError,match='duplicate_claim_identity'):
        evaluate(rows+[rows[0]])


@pytest.mark.parametrize('field,value', [('baseline',float('nan')),('baseline',float('inf')),
 ('signed_valence',float('nan')),('signed_valence',1.5),('baseline',True)])
def test_nonfinite_or_out_of_bounds(field,value):
    rows=synthetic()
    rows[0]=replace(rows[0],**{field:value})
    with pytest.raises(ValueError):evaluate(rows)


def test_groupless_or_underpowered_rejected():
    with pytest.raises(ValueError):evaluate([])
    with pytest.raises(ValueError):evaluate(synthetic(groups=3))


def test_zero_gain_ablation():
    out=evaluate(synthetic(),StudyPlan(gain=0))
    assert out['paired_gain_per_group']==0


def test_fake_receipt_string_no_authentication():
    rows=[replace(x,oracle_receipt_sha256='a'*64) for x in synthetic()]
    out=evaluate(rows)
    assert out['oracle_receipt_hashes_present']==len(rows)
    assert out['oracle_receipt_hashes_verified'] is False


def test_permutation_reproducibility_across_seeds():
    rows=synthetic()
    one=evaluate(rows,StudyPlan(seed=10))
    two=evaluate(rows,StudyPlan(seed=20))
    assert one['paired_gain_per_group']==two['paired_gain_per_group']
    assert one['sha256_pre_digest']!=two['sha256_pre_digest']


def test_invalid_resampling_plan():
    with pytest.raises(ValueError):evaluate(synthetic(),StudyPlan(permutation_repeats=0))
