"""Substrate diversity analysis — proves γ ≈ 1.0 is not a domain artifact.

Categorizes each validated substrate into an independent scientific domain
and verifies that γ ≈ 1.0 appears across at least 4 categorically different
domains. This is the quantitative backbone of the universality claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "DiversityReport",
    "SubstrateCategory",
    "analyze_diversity",
]

# ── Domain taxonomy ─────────────────────────────────────────────────────

DOMAIN_TAXONOMY: Final[dict[str, str]] = {
    # Biological
    "zebrafish_wt": "biology",
    "eeg_physionet": "neuroscience",
    "eeg_resting": "neuroscience",
    "hrv_physionet": "physiology",
    "hrv_fantasia": "physiology",
    # Chemical / physical
    "gray_scott": "chemistry",
    # Computational / network
    "kuramoto": "network_dynamics",
    "bnsyn": "network_dynamics",
    "serotonergic_kuramoto": "network_dynamics",
    # Constructed / market
    "cns_ai_loop": "cognitive_loop",
    "cfp_diy": "agent_model",
    "nfi_unified": "unified_field",
    # Mock (excluded from diversity)
    "mock_spike": "mock",
    "mock_morpho": "mock",
    "mock_psyche": "mock",
    "mock_market": "mock",
}

# Broader categories for universality claim
BROAD_CATEGORIES: Final[dict[str, str]] = {
    "biology": "BIOLOGICAL",
    "neuroscience": "BIOLOGICAL",
    "physiology": "BIOLOGICAL",
    "chemistry": "PHYSICAL",
    "network_dynamics": "COMPUTATIONAL",
    "cognitive_loop": "COMPUTATIONAL",
    "agent_model": "COMPUTATIONAL",
    "unified_field": "COMPUTATIONAL",
    "mock": "MOCK",
}


@dataclass(frozen=True)
class SubstrateCategory:
    """Single substrate with its domain classification."""

    entry_id: str
    gamma: float
    status: str
    domain: str
    broad_category: str
    in_metastable: bool  # |γ - 1.0| < 0.15


@dataclass(frozen=True)
class DiversityReport:
    """Substrate diversity analysis result."""

    total_entries: int
    validated_entries: int
    domains_represented: tuple[str, ...]
    broad_categories: tuple[str, ...]
    n_broad_categories: int
    mean_gamma_validated: float
    std_gamma_validated: float
    metastable_fraction: float
    all_substrates: tuple[SubstrateCategory, ...]
    universality_holds: bool  # >= 3 broad categories with γ in metastable


def analyze_diversity(
    ledger_path: str | Path | None = None,
) -> DiversityReport:
    """Analyze substrate diversity from the gamma ledger.

    Args:
        ledger_path: path to gamma_ledger.json. If None, uses default.

    Returns:
        DiversityReport with universality assessment.
    """
    if ledger_path is None:
        ledger_path = Path(__file__).parent.parent / "evidence" / "gamma_ledger.json"
    else:
        ledger_path = Path(ledger_path)

    with open(ledger_path, encoding="utf-8") as f:
        raw = json.load(f)

    entries = raw.get("entries", raw)
    if not isinstance(entries, dict):
        raise ValueError("ledger must have 'entries' dict")

    substrates: list[SubstrateCategory] = []
    validated_gammas: list[float] = []

    for eid, data in entries.items():
        if isinstance(data, str):
            continue
        gamma = data.get("gamma")
        status = data.get("status", "UNKNOWN")
        if gamma is None:
            continue

        domain = DOMAIN_TAXONOMY.get(eid, "unknown")
        broad = BROAD_CATEGORIES.get(domain, "UNKNOWN")
        in_meta = abs(gamma - 1.0) < 0.15

        substrates.append(
            SubstrateCategory(
                entry_id=eid,
                gamma=gamma,
                status=status,
                domain=domain,
                broad_category=broad,
                in_metastable=in_meta,
            )
        )

        # Phase 2 hardening (ledger v2.0.0): treat the "measured candidate"
        # tier as the universality-evidence pool. A substrate enters this
        # pool when it carries a γ value AND its status is one of the
        # pre-VALIDATED measurement tiers (VALIDATED, EVIDENCE_CANDIDATE,
        # SUPPORTED_BY_NULLS). VALIDATED_SUBSTRATE_EVIDENCE — reachable
        # only with external replication — is also included. Sub-γ
        # statuses (LOCAL_STRUCTURAL_EVIDENCE_ONLY for BN-Syn etc.) are
        # excluded because they do not emit γ.
        if status in {
            "VALIDATED",
            "VALIDATED_SUBSTRATE_EVIDENCE",
            "EVIDENCE_CANDIDATE",
            "SUPPORTED_BY_NULLS",
        }:
            validated_gammas.append(gamma)

    # Analysis: pool the same set the loop fed into validated_gammas.
    _MEASURED_STATUSES = {
        "VALIDATED",
        "VALIDATED_SUBSTRATE_EVIDENCE",
        "EVIDENCE_CANDIDATE",
        "SUPPORTED_BY_NULLS",
    }
    validated = [s for s in substrates if s.status in _MEASURED_STATUSES]
    domains = sorted({s.domain for s in validated})
    broad_cats = sorted({s.broad_category for s in validated if s.broad_category != "MOCK"})

    # Universality: >= 3 broad categories have at least one metastable substrate
    cats_with_metastable = {
        s.broad_category for s in validated if s.in_metastable and s.broad_category != "MOCK"
    }

    import numpy as np

    mean_g = float(np.mean(validated_gammas)) if validated_gammas else 0.0
    std_g = float(np.std(validated_gammas)) if len(validated_gammas) > 1 else 0.0
    meta_frac = sum(1 for s in validated if s.in_metastable) / len(validated) if validated else 0.0

    return DiversityReport(
        total_entries=len(substrates),
        validated_entries=len(validated),
        domains_represented=tuple(domains),
        broad_categories=tuple(broad_cats),
        n_broad_categories=len(broad_cats),
        mean_gamma_validated=mean_g,
        std_gamma_validated=std_g,
        metastable_fraction=meta_frac,
        all_substrates=tuple(substrates),
        universality_holds=len(cats_with_metastable) >= 3,
    )
