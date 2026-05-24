from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    SIGNED_LEDGER = "SIGNED_LEDGER"
    THIRD_PARTY_ATTESTATION = "THIRD_PARTY_ATTESTATION"
    SYSTEM_LOG = "SYSTEM_LOG"
    COUNTERFACTUAL_SIMULATION = "COUNTERFACTUAL_SIMULATION"
    MEMORY_TRACE = "MEMORY_TRACE"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def payload_hash(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    kind: EvidenceKind
    producer_id: str
    payload: dict[str, Any]
    payload_hash: str
    parent_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    timestamp_utc: str = ""
    signature: str | None = None

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id must be non-empty")
        if not self.producer_id.strip():
            raise ValueError("producer_id must be non-empty")
        if not self.timestamp_utc.strip():
            raise ValueError("timestamp_utc must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        if not self.payload_hash.startswith("sha256:"):
            raise ValueError("payload_hash must start with sha256:")
        computed = payload_hash(self.payload)
        if computed != self.payload_hash:
            raise ValueError(f"payload_hash mismatch for evidence node {self.node_id}")


@dataclass(frozen=True, slots=True)
class EvidenceGraph:
    nodes: tuple[EvidenceNode, ...] = ()

    def __post_init__(self) -> None:
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("EvidenceGraph contains duplicate node_id values")

        node_ids = set(ids)
        for node in self.nodes:
            missing = set(node.parent_ids) - node_ids
            if missing:
                missing_names = ", ".join(sorted(missing))
                raise ValueError(
                    f"Evidence node {node.node_id} references missing parents: {missing_names}"
                )

        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        parents = {node.node_id: set(node.parent_ids) for node in self.nodes}
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in permanent:
                return
            if node_id in temporary:
                raise ValueError("EvidenceGraph contains a cycle")
            temporary.add(node_id)
            for parent_id in parents[node_id]:
                visit(parent_id)
            temporary.remove(node_id)
            permanent.add(node_id)

        for node_id in parents:
            visit(node_id)

    def by_id(self) -> dict[str, EvidenceNode]:
        return {node.node_id: node for node in self.nodes}

    def require(self, node_ids: tuple[str, ...]) -> tuple[EvidenceNode, ...]:
        index = self.by_id()
        missing = tuple(node_id for node_id in node_ids if node_id not in index)
        if missing:
            missing_names = ", ".join(missing)
            raise ValueError(f"Missing evidence refs: {missing_names}")
        return tuple(index[node_id] for node_id in node_ids)

    def min_confidence(self, node_ids: tuple[str, ...] | None = None) -> float:
        selected = self.nodes if node_ids is None else self.require(node_ids)
        if not selected:
            return 0.0
        return min(node.confidence for node in selected)

    def producer_diversity(self, node_ids: tuple[str, ...] | None = None) -> int:
        selected = self.nodes if node_ids is None else self.require(node_ids)
        return len({node.producer_id for node in selected})

    def ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    def digest(self) -> str:
        payload = [
            {
                "node_id": node.node_id,
                "kind": node.kind.value,
                "producer_id": node.producer_id,
                "payload_hash": node.payload_hash,
                "parent_ids": node.parent_ids,
                "confidence": node.confidence,
                "timestamp_utc": node.timestamp_utc,
                "signature": node.signature,
            }
            for node in self.nodes
        ]
        return sha256_text(canonical_json(payload))
