"""Bridge: γ-ledger entry → EAI engine inputs.

Lifts an ``evidence/gamma_ledger.json`` entry into the gate's input
contract (``ClaimCard`` + ``BoundaryCard`` + ``ReproducibilityManifest``
+ contradiction markers + retention hash + revalidation flag) using a
pure, deterministic mapping. No network, no LLM, no PRNG.

The bridge is read-only: it never mutates the ledger. The gate's
verdict on a γ entry is a *measurement of how that entry currently
relates to the EAI discipline*, not a re-assertion of the entry's
status.

Routing policy (encoded by the mapping, executed by the gate):

* ``EVIDENCE`` ← entry has a real ``data_sha256`` AND no failure-state
  status tag.
* ``QUARANTINED`` ← entry's gate hash falls back to a metadata-only
  digest (no real data binding) **or** the entry is local-structural/
  numerical-internal only; revalidation is withheld so the gate routes
  the claim to the QUARANTINE basin.
* ``KILLED`` ← entry carries an explicit failure-state tag in its
  status (``EVIDENCE_CANDIDATE_NULL_FAILED``); the bridge prepends a
  ``[gate-tags: null_screen_rejected]`` header to the claim text and
  registers ``null_screen_rejected`` as a contradiction marker, so the
  falsification gate fires deterministically.

Forbidden: this bridge does NOT establish that the γ ledger is
scientifically validated, that EAI proves the γ scaling law, or that
the gate's verdict overrides the ledger's own status. It produces a
deterministic *measurement of admissibility under the EAI discipline*.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    ReproducibilityManifest,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class GammaGateInputs:
    """Container for the deterministic gate inputs derived from one
    γ-ledger entry. ``hash_bound`` records whether the artifact hash
    is bound to real data (True) or a metadata-only fallback (False).
    """

    claim: ClaimCard
    boundary: BoundaryCard
    reproducibility: ReproducibilityManifest
    contradiction_markers: list[str]
    retention_hash: str
    revalidation_passed: bool
    hash_bound: bool
    status_tags: list[str]


def _derive_status_tags(entry: dict[str, Any]) -> list[str]:
    """Map a ledger entry's status / tier / null-screen flags to a
    deterministic list of gate-relevant failure tags.

    Tags are *substrings of the gate-time claim text* (see
    ``_gate_claim_text``), so they trigger the falsification gate
    when registered as contradiction markers.
    """
    tags: list[str] = []
    status = str(entry.get("status") or "")
    tier = str(entry.get("evidence_tier") or "")
    if "NULL_FAILED" in status:
        tags.append("null_screen_rejected")
    if status == "LOCAL_STRUCTURAL_EVIDENCE_ONLY" or tier == "LOCAL_STRUCTURAL":
        tags.append("local_structural_only")
    if tier == "NUMERICAL_INTERNAL":
        tags.append("numerical_internal_only")
    return tags


def _gate_claim_text(entry: dict[str, Any], tags: list[str]) -> str:
    """Build the gate-time claim text. The base description is taken
    verbatim from the ledger; gate-only tags are prepended in a
    bracketed header so the gate's falsification scan can match them.
    The ledger entry itself is never mutated.
    """
    base = str(entry.get("description") or entry.get("substrate") or "")
    if not tags:
        return base
    header = "[gate-tags: " + ", ".join(tags) + "] "
    return header + base


def _artifact_hash_and_binding(entry: dict[str, Any], key: str) -> tuple[str, bool]:
    """Return ``(artifact_hash, hash_bound)``.

    The hash must be valid SHA-256 hex for the EAI engine's
    ``can_be_promoted`` check. If the ledger has a real ``data_sha256``
    we use it (``hash_bound=True``); otherwise we compute a deterministic
    metadata-only fallback so the engine does not crash, but flag the
    binding as missing so downstream routing can withhold revalidation.
    """
    raw = entry.get("data_sha256")
    if isinstance(raw, str) and _SHA256_HEX.fullmatch(raw):
        return raw, True
    fallback_input = (
        f"GAMMA-LEDGER-METADATA-ONLY:{key}:{entry.get('substrate', '')}:"
        f"{entry.get('derivation_method', '')}:{entry.get('status', '')}"
    )
    return hashlib.sha256(fallback_input.encode("utf-8")).hexdigest(), False


def ledger_entry_to_gate_inputs(
    key: str, entry: dict[str, Any], *, ledger_version: str
) -> GammaGateInputs:
    """Pure mapping: one ledger entry → one set of gate inputs."""

    tags = _derive_status_tags(entry)
    claim = ClaimCard(
        claim_id=f"GAMMA-{key.upper().replace('_', '-')}",
        claim_text=_gate_claim_text(entry, tags),
        claim_type=ClaimType.STATISTICAL,
    )

    substrate = str(entry.get("substrate") or "unknown_substrate")
    # Invariant: tested_conditions must be a subset of valid_for
    # (see ``EvidenceArtifact.can_be_promoted``). The substrate
    # itself is what was tested. derivation_method is methodology,
    # not a boundary axis, so it lives in the reproducibility
    # manifest's ``commands`` instead of on the boundary card.
    boundary = BoundaryCard(
        boundary_id=f"BND-GAMMA-{key.upper().replace('_', '-')}",
        valid_for=[substrate],
        invalid_for=[
            "global_extrapolation",
            "cross_substrate_pooling",
            "unrestricted_universal",
        ],
        tested_conditions=[substrate],
        untested_conditions=["other_substrates", "out_of_distribution_inputs"],
    )

    artifact_hash, hash_bound = _artifact_hash_and_binding(entry, key)
    derivation = str(entry.get("derivation_method") or "unspecified_derivation")
    reproducibility = ReproducibilityManifest(
        commands=[
            str(entry.get("rerun_command") or "no_rerun_command_specified"),
            f"derivation:{derivation}",
        ],
        environment=f"gamma_ledger_v{ledger_version}",
        artifact_hash=artifact_hash,
    )

    # The contradiction markers are the same tags surfaced in the
    # gate-time claim text header, so the falsification gate fires
    # iff the entry carries one of the failure-state flags. Clean
    # entries pass falsification.
    contradiction_markers = list(tags)

    retention_hash = "a" * 64  # boundary scaffold; ledger pinning
    # done via artifact_hash + dataset sha in the report.

    # Routing:
    #   - tags non-empty (e.g. NULL_FAILED)  -> KILLED (falsification)
    #   - hash NOT bound to real data        -> QUARANTINED via
    #     revalidation_passed=False
    #   - clean + hash bound                 -> EVIDENCE
    if tags:
        revalidation_passed = False  # immaterial — falsifier kills first
    elif not hash_bound:
        revalidation_passed = False  # withhold to land in QUARANTINE
    else:
        revalidation_passed = True

    return GammaGateInputs(
        claim=claim,
        boundary=boundary,
        reproducibility=reproducibility,
        contradiction_markers=contradiction_markers,
        retention_hash=retention_hash,
        revalidation_passed=revalidation_passed,
        hash_bound=hash_bound,
        status_tags=tags,
    )


def load_ledger(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """Load the γ ledger, returning (version, entries)."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    version = str(raw.get("version", "unknown"))
    entries = raw.get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("gamma ledger 'entries' must be a JSON object")
    return version, entries
