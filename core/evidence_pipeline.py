"""Unified evidence pipeline — collect, validate, register, query.

Evidence flow: measure → validate → register → query.
Registry is append-only. Invalid evidence rejected with reason.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404  # used only for hardcoded git command
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.evidence_schema import EvidenceRecord, record_to_dict, validate_record

__all__ = [
    "EvidencePipeline",
    "RawEvidence",
    "ValidatedEvidence",
]


@dataclass(frozen=True)
class RawEvidence:
    substrate: str
    metric: str
    value: float
    ci95_lo: float
    ci95_hi: float
    method: str
    source: str


@dataclass(frozen=True)
class ValidatedEvidence:
    record: EvidenceRecord
    validation_errors: tuple[str, ...]


class EvidencePipeline:
    """Unified evidence collection, validation, registration pipeline."""

    def __init__(self, evidence_dir: Path | None = None) -> None:
        self._root = evidence_dir or Path(__file__).resolve().parent.parent / "evidence"
        self._registry_path = self._root / "registry.json"

    def collect(self, source: str, **kwargs: float | str) -> RawEvidence:
        """Create raw evidence from measurement source."""
        return RawEvidence(
            substrate=str(kwargs.get("substrate", "")),
            metric=str(kwargs.get("metric", "")),
            value=float(kwargs.get("value", float("nan"))),
            ci95_lo=float(kwargs.get("ci95_lo", float("nan"))),
            ci95_hi=float(kwargs.get("ci95_hi", float("nan"))),
            method=str(kwargs.get("method", "")),
            source=source,
        )

    def validate(self, raw: RawEvidence) -> ValidatedEvidence:
        """Validate raw evidence against schema. Returns ValidatedEvidence."""
        git_sha = self._get_git_sha()
        record = EvidenceRecord(
            substrate=raw.substrate,
            metric=raw.metric,
            value=raw.value,
            ci95_lo=raw.ci95_lo,
            ci95_hi=raw.ci95_hi,
            method=raw.method,
            timestamp=time.time(),
            git_sha=git_sha,
        )
        valid, errors = validate_record(record)
        return ValidatedEvidence(record=record, validation_errors=tuple(errors))

    def register(self, evidence: ValidatedEvidence) -> bool:
        """Register validated evidence. Append-only to registry.json. Returns success."""
        if evidence.validation_errors:
            return False

        registry = self._load_registry()
        records = registry.get("records", [])
        records.append(record_to_dict(evidence.record))
        registry["records"] = records
        self._save_registry(registry)
        return True

    def manifest(self, session_id: str) -> dict[str, Any]:
        """Generate evidence manifest for a session."""
        manifests_dir = self._root / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)

        registry = self._load_registry()
        manifest = {
            "session_id": session_id,
            "timestamp": time.time(),
            "n_records": len(registry.get("records", [])),
            "records": registry.get("records", []),
        }

        manifest_path = manifests_dir / f"manifest_{session_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    def query(
        self, substrate: str | None = None, metric: str | None = None
    ) -> list[dict[str, Any]]:
        """Query evidence records by substrate and/or metric."""
        registry = self._load_registry()
        records = registry.get("records", [])

        results = []
        for r in records:
            if substrate and r.get("substrate") != substrate:
                continue
            if metric and r.get("metric") != metric:
                continue
            results.append(r)
        return results

    def _load_registry(self) -> dict[str, Any]:
        if self._registry_path.exists():
            result: dict[str, Any] = json.loads(self._registry_path.read_text())
            return result
        return {"version": "1.0.0", "records": []}

    def _save_registry(self, registry: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(json.dumps(registry, indent=2, default=str))

    @staticmethod
    def _get_git_sha() -> str:
        try:
            result = subprocess.run(  # nosec B603 B607  # hardcoded git command, no user input
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"
