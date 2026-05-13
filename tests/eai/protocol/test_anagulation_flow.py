from core.eai.anagulation import anagulate_claim


def test_anagulation_kills_falsification_failure() -> None:
    result = anagulate_claim(
        claim_id="CLM-ANAG-1",
        claim_text="perpetual motion machine",
        contradiction_markers=[],
        reproducibility_ok=True,
    )
    assert result.status == "KILLED"
    assert result.kill_artifact is not None
    assert result.kill_artifact.failed_test == "physical_plausibility_violation"


def test_anagulation_kills_missing_reproducibility() -> None:
    result = anagulate_claim(
        claim_id="CLM-ANAG-2",
        claim_text="bounded local claim",
        contradiction_markers=[],
        reproducibility_ok=False,
    )
    assert result.status == "KILLED"
    assert result.kill_artifact is not None
    assert result.kill_artifact.kill_reason == "reproducibility_missing"


def test_anagulation_allows_verified_claim() -> None:
    result = anagulate_claim(
        claim_id="CLM-ANAG-3",
        claim_text="bounded local claim",
        contradiction_markers=["fake citation"],
        reproducibility_ok=True,
    )
    assert result.status == "EVIDENCE"
    assert result.kill_artifact is None
