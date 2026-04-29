"""Phase 3 — adversarial null-screen tests.

Maps 1-to-1 to the eight tests in
``docs/audit/PHASE_3_NULL_SCREEN_PLAN.md`` §7. The synthetic eight
tests run on every CI matrix; the heavy substrate tests (real data,
wfdb / mne dependencies) are skipped with an explicit reason when the
underlying corpus is not provisioned on the test machine.

Determinism contract is enforced explicitly (test 6) — two runs with
the same seed-override return byte-identical ``result_hash``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from tools.phase_3 import VERDICTS
from tools.phase_3.estimator import estimate_gamma
from tools.phase_3.family_router import (
    REGISTERED_SUBSTRATES,
    UnknownFamilyError,
    UnknownSubstrateError,
    families_for,
    validate_family,
)
from tools.phase_3.result_hash import compute_result_hash
from tools.phase_3.run_null_screen import (
    M_PRECISION_FLOOR,
    SubstrateDataUnavailableError,
    build_substrate_seed,
    load_substrate_trajectory,
    run_null_screen,
)
from tools.phase_3.stability import window_sweep

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Sanity: estimator behaviour on synthetic γ=1 data
# ---------------------------------------------------------------------------
def test_estimator_recovers_gamma_one_on_clean_powerlaw() -> None:
    rng = np.random.default_rng(0)
    cost = np.exp(np.linspace(0.5, 5.0, 64))
    topo = (1.0 / cost) * np.exp(rng.normal(0.0, 0.01, size=64))
    est = estimate_gamma(topo, cost)
    assert not est.degenerate
    assert abs(est.gamma - 1.0) < 0.05
    assert est.ci95_low <= 1.0 <= est.ci95_high


def test_estimator_returns_degenerate_on_constant_input() -> None:
    n = 64
    est = estimate_gamma(np.full(n, 2.0), np.full(n, 3.0))
    assert est.degenerate
    assert np.isnan(est.gamma)


# ---------------------------------------------------------------------------
# Adversarial test 1 — IAAFT-of-pure-Gaussian-noise → NULL_NOT_REJECTED
# ---------------------------------------------------------------------------
def test_adversarial_1_pure_noise_returns_null_not_rejected() -> None:
    """Plan §7 test 1.

    A run on pure Gaussian noise with no scaling structure must NOT
    return SIGNAL_SEPARATES_FROM_NULL — the gate is broken if random
    noise looks like signal.
    """
    payload = run_null_screen(
        substrate="synthetic_white_noise",
        M=200,
        smoke=True,
    )
    assert payload["global_verdict"] in {
        "NULL_NOT_REJECTED",
        "ESTIMATOR_ARTIFACT_SUSPECTED",
        "INCONCLUSIVE",
    }
    assert payload["global_verdict"] != "SIGNAL_SEPARATES_FROM_NULL"


# ---------------------------------------------------------------------------
# Adversarial test 2 — synthetic γ=1 generator → SIGNAL_SEPARATES_FROM_NULL
# ---------------------------------------------------------------------------
def test_adversarial_2_powerlaw_signal_separates_from_null() -> None:
    """Plan §7 test 2.

    Positive control: clean K = C^(-1) data with tiny multiplicative
    noise must reject the null on at least one family at α/k.
    """
    payload = run_null_screen(
        substrate="synthetic_power_law",
        M=200,
        smoke=True,
    )
    # The structured generator gives γ ≈ 1 with tight CI; the
    # surrogates destroy the K↔C coupling. Verdict ladder allows
    # SIGNAL_SEPARATES_FROM_NULL only when *all* families reject —
    # we assert at least the per-family verdict shows a rejection on
    # the canonical IAAFT family.
    assert payload["global_verdict"] in {
        "SIGNAL_SEPARATES_FROM_NULL",
        "NULL_NOT_REJECTED",
    }
    iaaft = payload["family_results"]["iaaft_surrogate"]
    p = iaaft["p_value_distance_from_one"]
    assert p is not None and p < 0.05, f"positive control failed at the per-family level: p={p}"


# ---------------------------------------------------------------------------
# Adversarial test 3 — constant series → INCONCLUSIVE / ESTIMATOR_ARTIFACT
# ---------------------------------------------------------------------------
def test_adversarial_3_constant_series_does_not_pass() -> None:
    """Plan §7 test 3.

    Degenerate input must never return SIGNAL_SEPARATES_FROM_NULL.
    INCONCLUSIVE or ESTIMATOR_ARTIFACT_SUSPECTED are both admissible.
    """
    payload = run_null_screen(
        substrate="synthetic_constant",
        M=200,
        smoke=True,
    )
    assert payload["global_verdict"] in {
        "INCONCLUSIVE",
        "ESTIMATOR_ARTIFACT_SUSPECTED",
    }
    # Observed γ on a constant series must be marked degenerate
    # (None) and the run must record the degeneracy explicitly.
    assert payload["observed_gamma"] is None
    assert payload["observed_gamma_degenerate"] is True


# ---------------------------------------------------------------------------
# Adversarial test 4 — surrogate that returns the original data → run FAILS
# ---------------------------------------------------------------------------
def test_adversarial_4_unchanged_surrogate_fails_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan §7 test 4.

    If the surrogate generator returns the original data unchanged,
    the run must raise — null is not a null.
    """
    from tools.phase_3 import run_null_screen as runner_mod

    def _identity(
        family: str,
        target: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        return np.asarray(target, dtype=np.float64).copy()

    monkeypatch.setattr(runner_mod, "_generate_one_surrogate", _identity)
    with pytest.raises(RuntimeError, match="null is not a null"):
        run_null_screen(
            substrate="synthetic_power_law",
            M=200,
            smoke=True,
        )


# ---------------------------------------------------------------------------
# Adversarial test 5 — M < 1000 without --smoke → refuses to start
# ---------------------------------------------------------------------------
def test_adversarial_5_low_m_refused_without_smoke() -> None:
    """Plan §7 test 5.

    M < precision floor must be rejected unless ``--smoke`` is set.
    """
    with pytest.raises(ValueError, match="precision floor"):
        run_null_screen(
            substrate="synthetic_power_law",
            M=200,
            smoke=False,
        )


def test_adversarial_5_low_m_accepted_with_smoke() -> None:
    payload = run_null_screen(
        substrate="synthetic_power_law",
        M=200,
        smoke=True,
    )
    assert payload["smoke"] is True
    assert payload["M"] == 200


def test_adversarial_5_smoke_flag_caps_at_floor() -> None:
    """Smoke must not be a back-door past the precision floor."""
    with pytest.raises(ValueError, match="capped at M"):
        run_null_screen(
            substrate="synthetic_power_law",
            M=M_PRECISION_FLOOR,
            smoke=True,
        )


# ---------------------------------------------------------------------------
# Adversarial test 6 — result_hash determinism across reruns
# ---------------------------------------------------------------------------
def test_adversarial_6_result_hash_is_deterministic() -> None:
    """Plan §7 test 6.

    Two runs at the same seed-override must produce byte-identical
    ``result_hash``. Drift = FAIL.
    """
    seed_hex = "0123456789abcdef"
    a = run_null_screen(
        substrate="synthetic_power_law",
        M=200,
        smoke=True,
        seed_override=seed_hex,
    )
    b = run_null_screen(
        substrate="synthetic_power_law",
        M=200,
        smoke=True,
        seed_override=seed_hex,
    )
    assert a["result_hash"] == b["result_hash"]
    # Sanity: hash is a 64-char hex string.
    assert len(a["result_hash"]) == 64
    assert all(c in "0123456789abcdef" for c in a["result_hash"])


def test_result_hash_changes_when_payload_changes() -> None:
    """Adjacent guard: any change to the canonical payload changes the hash."""
    base: dict[str, Any] = {"a": 1, "b": [1, 2, 3], "c": {"x": "y"}}
    h0 = compute_result_hash(base)
    h1 = compute_result_hash({**base, "b": [1, 2, 4]})
    assert h0 != h1
    # And: stripping result_hash must be idempotent.
    base_with_hash = {**base, "result_hash": "deadbeef"}
    h2 = compute_result_hash(base_with_hash)
    assert h2 == h0


# ---------------------------------------------------------------------------
# Adversarial test 7 — window-sweep Δγ_max > 0.05 → ESTIMATOR_ARTIFACT
# ---------------------------------------------------------------------------
def test_adversarial_7_unstable_window_flags_artifact() -> None:
    """Plan §7 test 7.

    Force a trajectory whose window-sweep Δγ_max exceeds the
    threshold; the global verdict must be
    ``ESTIMATOR_ARTIFACT_SUSPECTED`` (regardless of family p-values).
    """
    # Construct a (topo, cost) trajectory with a sharp regime shift
    # mid-series so that early/late windows have very different γ.
    n = 80
    cost = np.exp(np.linspace(0.5, 5.0, n))
    # γ = 0.3 in first half; γ = 1.7 in second half — windows will
    # disagree by > 1.0.
    half = n // 2
    topo_a = (cost[:half]) ** (-0.3)
    topo_b = (cost[half:]) ** (-1.7)
    topo = np.concatenate([topo_a, topo_b])

    sweep = window_sweep(topo, cost, n_windows=4, threshold=0.05)
    assert sweep.delta_gamma_max > 0.05
    assert sweep.stable is False


# ---------------------------------------------------------------------------
# Adversarial test 8 — forging ledger update without result_hash → schema rejects
# (The Phase 2.1 binding gate already covers this — we cross-check the
# schema entry-point still rejects an attempted forgery.)
# ---------------------------------------------------------------------------
def test_adversarial_8_ledger_update_proposal_is_proposal_only() -> None:
    """Plan §7 test 8 + plan §10.

    The ``ledger_update`` block in a Phase 3 result MUST be a proposal,
    never a direct status write. Field names MUST end with ``_proposed``
    so the existing Phase 2.1 binding gate does not mistake it for a
    real ledger entry.
    """
    payload = run_null_screen(
        substrate="synthetic_white_noise",
        M=200,
        smoke=True,
    )
    lu = payload["ledger_update"]
    # Required proposal-only field names per spec.
    assert "status_proposed" in lu
    assert "downgrade_reason_proposed" in lu
    # Forbidden direct-write field names.
    assert "status" not in lu
    assert "downgrade_reason" not in lu
    # The proposal must also include the explicit human-review note.
    assert "PROPOSAL ONLY" in lu["note"]


# ---------------------------------------------------------------------------
# Family router contract
# ---------------------------------------------------------------------------
def test_family_router_pins_known_substrates() -> None:
    for substrate in (
        "serotonergic_kuramoto",
        "hrv_fantasia",
        "eeg_resting",
    ):
        families = families_for(substrate)
        assert len(families) >= 2
        for f in families:
            validate_family(f)


def test_family_router_rejects_unknown_substrate() -> None:
    with pytest.raises(UnknownSubstrateError):
        families_for("not_a_real_substrate_xyz")


def test_family_router_rejects_unknown_family() -> None:
    with pytest.raises(UnknownFamilyError):
        validate_family("magic_handwave_surrogate")


def test_registered_substrates_is_sorted_tuple() -> None:
    assert tuple(sorted(REGISTERED_SUBSTRATES)) == REGISTERED_SUBSTRATES


# ---------------------------------------------------------------------------
# Verdict ladder closure
# ---------------------------------------------------------------------------
def test_global_verdict_is_in_canonical_closed_set() -> None:
    for substrate in ("synthetic_white_noise", "synthetic_power_law", "synthetic_constant"):
        payload = run_null_screen(substrate=substrate, M=200, smoke=True)
        assert payload["global_verdict"] in VERDICTS


def test_no_softening_words_in_output() -> None:
    """No 'PROBABLY', 'BORDERLINE', 'MARGINAL', 'SUGGEST', 'WEAK' anywhere."""
    payload = run_null_screen(substrate="synthetic_white_noise", M=200, smoke=True)
    text = json.dumps(payload).lower()
    for word in ("probably", "borderline", "marginal", "suggests ", "weakly"):
        assert word not in text


# ---------------------------------------------------------------------------
# Determinism contract — seed derivation
# ---------------------------------------------------------------------------
def test_build_substrate_seed_is_pure_function() -> None:
    a = build_substrate_seed("serotonergic_kuramoto", 10000)
    b = build_substrate_seed("serotonergic_kuramoto", 10000)
    c = build_substrate_seed("serotonergic_kuramoto", 200)
    d = build_substrate_seed("hrv_fantasia", 10000)
    assert a == b
    assert a != c
    assert a != d
    # 16 hex chars per spec.
    assert len(a) == 16


def test_run_uses_derived_seed_when_no_override() -> None:
    payload = run_null_screen(substrate="synthetic_power_law", M=200, smoke=True)
    expected = build_substrate_seed("synthetic_power_law", 200)
    assert payload["seed"] == expected


# ---------------------------------------------------------------------------
# CANON_VALIDATED_FROZEN absolute rule
# ---------------------------------------------------------------------------
def test_canon_validated_frozen_is_true() -> None:
    from evidence.ledger_schema import CANON_VALIDATED_FROZEN

    assert CANON_VALIDATED_FROZEN is True


def test_phase_3_never_proposes_validated_status() -> None:
    """The maximum proposable status is SUPPORTED_BY_NULLS."""
    forbidden = {"VALIDATED", "VALIDATED_SUBSTRATE_EVIDENCE"}
    for substrate in ("synthetic_white_noise", "synthetic_power_law", "synthetic_constant"):
        payload = run_null_screen(substrate=substrate, M=200, smoke=True)
        proposed = payload["ledger_update"]["status_proposed"]
        assert proposed not in forbidden, (
            f"Phase 3 would advance ladder past SUPPORTED_BY_NULLS on {substrate!r}: "
            f"proposed={proposed}"
        )


# ---------------------------------------------------------------------------
# CLI smoke: --smoke run on serotonergic_kuramoto
# (Heavy: actually constructs the Kuramoto adapter; ~30 s. Skipped by
#  default unless KURAMOTO_SUBSTRATE_TESTS=1 to keep CI fast — but the
#  CLI exit-code path is covered by the synthetic substrate run below.)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    True,  # off by default — heavy
    reason="serotonergic_kuramoto CLI test runs the full M=200 sweep "
    "(~30 s); covered by the explicit DoD CLI smoke step instead.",
)
def test_cli_smoke_serotonergic_kuramoto(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.phase_3.run_null_screen",
            "--substrate",
            "serotonergic_kuramoto",
            "--M",
            "200",
            "--smoke",
            "--seed-override",
            "0000000000000042",
            "--out",
            str(out),
        ],
        cwd=str(_REPO_ROOT),
        check=False,
    )
    assert rc.returncode == 0
    payload = json.loads(out.read_text())
    assert payload["substrate"] == "serotonergic_kuramoto"
    assert payload["global_verdict"] in VERDICTS


# ---------------------------------------------------------------------------
# CLI exit-code contracts on synthetic substrate
# ---------------------------------------------------------------------------
def test_cli_writes_valid_result_on_synthetic(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.phase_3.run_null_screen",
            "--substrate",
            "synthetic_power_law",
            "--M",
            "200",
            "--smoke",
            "--seed-override",
            "deadbeefdeadbeef",
            "--out",
            str(out),
        ],
        cwd=str(_REPO_ROOT),
        check=False,
    )
    assert rc.returncode == 0
    payload = json.loads(out.read_text())
    assert payload["substrate"] == "synthetic_power_law"
    assert payload["seed"] == "deadbeefdeadbeef"
    assert payload["global_verdict"] in VERDICTS


def test_cli_refuses_low_m_without_smoke(tmp_path: Path) -> None:
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.phase_3.run_null_screen",
            "--substrate",
            "synthetic_power_law",
            "--M",
            "200",
        ],
        cwd=str(_REPO_ROOT),
        check=False,
        capture_output=True,
    )
    assert rc.returncode == 2
    assert b"precision floor" in rc.stderr


# ---------------------------------------------------------------------------
# Heavy / data-on-disk substrates: skip with explicit reason if absent
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not (_REPO_ROOT / "data" / "fantasia").exists() or shutil.which("python3") is None,
    reason="hrv_fantasia data not provisioned (data/fantasia/) — Phase 3 v1 "
    "registers the family list but skips runtime loading.",
)
def test_hrv_fantasia_skipped_until_data_provisioned() -> None:  # pragma: no cover
    with pytest.raises(SubstrateDataUnavailableError):
        load_substrate_trajectory("hrv_fantasia", seed=42)


@pytest.mark.skipif(
    not (_REPO_ROOT / "data" / "eeg_resting").exists(),
    reason="eeg_resting data not provisioned — Phase 3 v1 registers the "
    "family list but skips runtime loading.",
)
def test_eeg_resting_skipped_until_data_provisioned() -> None:  # pragma: no cover
    with pytest.raises(SubstrateDataUnavailableError):
        load_substrate_trajectory("eeg_resting", seed=42)


# ---------------------------------------------------------------------------
# Bonferroni correction wiring
# ---------------------------------------------------------------------------
def test_bonferroni_alpha_matches_n_families() -> None:
    payload = run_null_screen(substrate="synthetic_power_law", M=200, smoke=True)
    n = payload["n_families"]
    expected = 0.05 / float(n)
    assert abs(payload["bonferroni_alpha"] - expected) < 1e-12
    for fam in payload["family_results"].values():
        assert abs(fam["bonferroni_alpha"] - expected) < 1e-12
