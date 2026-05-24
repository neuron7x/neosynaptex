from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(json.dumps(payload, indent=2))
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def claim_artifact_name(route_mode: str, final_status: str) -> str:
    if final_status == "CLOSED":
        return "closure_artifact.json"
    if final_status == "QUARANTINED":
        return "quarantine_artifact.json"
    if final_status == "REJECTED":
        return "rejection_artifact.json"
    if route_mode == "escalate":
        return "escalation_trace.json"
    return "closure_artifact.json"
