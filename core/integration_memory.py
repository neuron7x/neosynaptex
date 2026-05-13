from __future__ import annotations

import copy


class IntegrationMemory:
    """Minimal integration-memory store guarded by claim status with rollback support."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, object]] = {}
        self._snapshots: dict[str, dict[str, dict[str, object]]] = {}

    def apply_patch(self, *, claim_id: str, status: str, patch: dict[str, object]) -> bool:
        if status != "EVIDENCE":
            return False
        self._store[claim_id] = patch
        return True

    def get(self, claim_id: str) -> dict[str, object] | None:
        return self._store.get(claim_id)

    def snapshot(self, tag: str) -> None:
        self._snapshots[tag] = copy.deepcopy(self._store)

    def rollback(self, tag: str) -> bool:
        snap = self._snapshots.get(tag)
        if snap is None:
            return False
        self._store = copy.deepcopy(snap)
        return True
