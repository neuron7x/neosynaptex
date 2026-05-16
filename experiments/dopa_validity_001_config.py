"""DOPA-VALIDITY-001 — single source of truth for all constants.

Every constant used by ``experiments/dopa_validity_001.py`` and
``tests/test_dopa_validity_001.py`` is defined *here only*. Duplicating any of
these values in either module is a construct-validity break (config/code SSOT
drift was an explicit invalidator in evidence/dopa_closure/RETRACTION.md) and is
asserted against by the test-suite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

# --- Identity -------------------------------------------------------------
EXPERIMENT_ID: Final[str] = "DOPA-VALIDITY-001"

CLAIM: Final[str] = (
    "An actual DNCA/dopamine-derived signed vRPE predicts verification benefit "
    "better than uncertainty/margin, under an admissible verifier and a true "
    "sign-flip negative control."
)

BOUNDARY: Final[str] = (
    "Scoped strictly to: the executable neuron7x_agents DopamineOperator value-net "
    "TD error, a deterministic arithmetic-closure verifier micro-task, and the "
    "policies enumerated in this module. No claim about DOPA-CLOSURE the theory; "
    "no claim beyond this exact implementation."
)

# --- DNCA / dopamine signal source ---------------------------------------
DNCA_SIGNAL_MODULE: Final[str] = "neuron7x_agents.dnca.neuromodulators.dopamine"
DNCA_SIGNAL_SYMBOL: Final[str] = "DopamineOperator"
# DopamineOperator emits a signed pre-asymmetric RPE on the "valence" field
# (delta clamped to [-1, 1], BEFORE the Schultz asymmetric gain). That signed
# field — not the asymmetric-gained, non-negative-collapsing "dopamine_signal"
# — is the signed vRPE under test.
SIGNED_VRPE_FIELD: Final[str] = "valence"

STATE_DIM: Final[int] = 16
HIDDEN_DIM: Final[int] = 32

# --- Task / verifier ------------------------------------------------------
SEED: Final[int] = 9790979
N_ITEMS: Final[int] = 240
N_SEEDS: Final[int] = 12  # independent task draws for the routing significance test
# Verification budget: only this fraction of items may be verified per policy.
BUDGET_FRACTION: Final[float] = 0.30

# --- Admissibility thresholds (pre-registered, no post-hoc tuning) --------
# Step B2: the *routed* signal (-vRPE) must be truth-correlated with
# verification benefit (Spearman) at this two-sided alpha. Per RETRACTION
# precondition #3 the estimator must be shown truth-correlated *independently*
# and *before* any routing comparison — so B2 is evaluated on its own seed band
# disjoint from the Step-D decision draws, and must hold robustly across them,
# not on a single borderline draw.
VRPE_TRUTH_CORR_ALPHA: Final[float] = 0.01
# B2 independence: a dedicated seed band, offset far from SEED so it cannot
# overlap the Step-D routing seeds [SEED, SEED+N_SEEDS).
B2_SEED_OFFSET: Final[int] = 1_000_003
N_B2_SEEDS: Final[int] = 12
# Fail-closed robustness: the routed correlation must be significant
# (p < VRPE_TRUTH_CORR_ALPHA) AND positive on *every* independent B2 seed.
# A single fragile/borderline draw never licenses reading a KILL.
B2_REQUIRED_FRACTION: Final[float] = 1.0
# Step D: minimum pre-registered advantage of dopa over uncertainty_only,
# expressed as a fraction of total recoverable verification benefit.
DELTA_MIN: Final[float] = 0.05
# Step D: significance threshold for the paired dopa-vs-uncertainty test.
ALPHA: Final[float] = 0.01

# --- Verdict vocabulary (mirrors the schema enum; single source) ---------
VERDICT_INADMISSIBLE_NO_SIGNAL: Final[str] = "INADMISSIBLE_MISSING_DNCA_EXECUTABLE_SIGNAL"
VERDICT_INADMISSIBLE_WEAK_VERIFIER: Final[str] = "INADMISSIBLE_WEAK_VERIFIER"
VERDICT_INADMISSIBLE_METRIC_COLLAPSE: Final[str] = "INADMISSIBLE_METRIC_COLLAPSE"
VERDICT_KILLED: Final[str] = "KILLED"
VERDICT_SURVIVED: Final[str] = "SURVIVED_INITIAL"

ALL_VERDICTS: Final[tuple[str, ...]] = (
    VERDICT_INADMISSIBLE_NO_SIGNAL,
    VERDICT_INADMISSIBLE_WEAK_VERIFIER,
    VERDICT_INADMISSIBLE_METRIC_COLLAPSE,
    VERDICT_KILLED,
    VERDICT_SURVIVED,
)

POLICIES: Final[tuple[str, ...]] = (
    "dopa_signed_vrpe",
    "uncertainty_only",
    "no_vRPE",
    "signed_vrpe_inverted",
    "random_gate",
    "verify_all",
)

# --- Paths ----------------------------------------------------------------
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVIDENCE_DIR: Final[Path] = _REPO_ROOT / "evidence" / "dopa_closure"
SCHEMA_PATH: Final[Path] = _REPO_ROOT / "schemas" / "dopa_validity_001_result.schema.json"
RESULT_PATH: Final[Path] = EVIDENCE_DIR / "dopa_validity_001_result.json"
INADMISSIBLE_PATH: Final[Path] = EVIDENCE_DIR / "INADMISSIBLE_DOPA_VALIDITY_001.json"
KILL_PATH: Final[Path] = EVIDENCE_DIR / "KILL-0979B_DNCA_DOPA_ROUTING.json"
SURVIVED_PATH: Final[Path] = EVIDENCE_DIR / "SURVIVED_INITIAL_DOPA_VALIDITY_001.json"


def config_hash() -> str:
    """Deterministic hash of this SSOT file's bytes — pins every constant."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
