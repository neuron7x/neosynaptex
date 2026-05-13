from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

Clock = Callable[[], str]


def _utc_now_iso() -> str:
    """Default wall-clock for ledger timestamps (UTC ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LedgerEntry:
    artifact_id: str
    claim_id: str
    status: str
    retention_hash: str
    timestamp_utc: str


class ArtifactLedger:
    """Append-only artifact ledger for auditability.

    The optional ``clock`` callable controls the source of
    ``timestamp_utc`` on every appended entry. The default reads
    real UTC wall-clock; benchmarks and replay tests inject a fixed
    clock to produce bit-identical ledger transcripts.
    """

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._entries: list[LedgerEntry] = []
        self._clock: Clock = clock if clock is not None else _utc_now_iso

    def append(
        self, artifact_id: str, claim_id: str, status: str, retention_hash: str
    ) -> LedgerEntry:
        if not re.fullmatch(r"[0-9a-f]{64}", retention_hash or ""):
            raise ValueError("retention_hash must be lowercase SHA-256 hex")
        entry = LedgerEntry(
            artifact_id=artifact_id,
            claim_id=claim_id,
            status=status,
            retention_hash=retention_hash,
            timestamp_utc=self._clock(),
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)
