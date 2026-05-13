from __future__ import annotations

import os
import re

from core.eai.intelligence_cycle import EvidenceArtifact


def _is_sha256_hex(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


def _emergency_exit_enabled() -> bool:
    return os.getenv("EAI_EMERGENCY_EXIT", "").strip().lower() in {"1", "true", "yes", "on"}


def decide_intent_update(
    artifact: EvidenceArtifact,
    *,
    retention_hash: str | None,
    revalidation_passed: bool,
) -> str:
    if _emergency_exit_enabled():
        return "QUARANTINED"
    if not artifact.can_be_promoted():
        return "KILLED"
    if not _is_sha256_hex(retention_hash or ""):
        return "QUARANTINED"
    if not revalidation_passed:
        return "QUARANTINED"
    return "EVIDENCE"
