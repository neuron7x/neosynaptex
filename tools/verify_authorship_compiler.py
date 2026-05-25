from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml


class InvariantError(RuntimeError):
    pass


def _run_git(args: list[str]) -> str:
    out = subprocess.check_output(["git", *args], text=True)
    return out.strip()


def _changed_files(base_ref: str) -> list[str]:
    out = _run_git(["diff", "--name-only", f"{base_ref}...HEAD"])
    return [line for line in out.splitlines() if line.strip()]


def _load_config(path: Path) -> dict[str, Any]:
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise InvariantError(f"config root must be a mapping: {path}")
    return cast(dict[str, Any], raw)


def _is_allowed_path(path: str, allowed: list[str]) -> bool:
    return any(path == a or path.startswith(a) for a in allowed)


def _check_i1(changed: list[str], allowed_top_level: list[str]) -> None:
    for path in changed:
        if not _is_allowed_path(path, allowed_top_level):
            raise InvariantError(f"I1 fail: disallowed path '{path}'")


def _check_i2(
    changed: list[str],
    forbidden_patterns: list[str],
    ignored_paths: list[str] | None = None,
) -> None:
    ignored = ignored_paths or []
    regexes = [re.compile(p) for p in forbidden_patterns]
    for path in changed:
        if _is_allowed_path(path, ignored):
            continue
        p = Path(path)
        if not p.exists() or p.is_dir():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for rgx in regexes:
            if rgx.search(text):
                raise InvariantError(f"I2 fail: forbidden pattern '{rgx.pattern}' in {path}")


def _count_public_tokens(changed: list[str], exclude_paths: list[str] | None = None) -> int:
    excluded = exclude_paths or []
    total = 0
    for path in changed:
        if _is_allowed_path(path, excluded):
            continue
        p = Path(path)
        if not p.exists() or p.is_dir():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        total += len(text.split())
    return total


def _count_verified_edges(changed: list[str]) -> int:
    count = 0
    for path in changed:
        if not path.startswith("tests/"):
            continue
        p = Path(path)
        if not p.exists() or p.is_dir():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        count += txt.count("assert ") + txt.count("pytest")
    return count


def _check_i6(
    changed: list[str],
    min_verified_edges: int,
    max_public_tokens: int,
    public_token_exclude_paths: list[str] | None = None,
) -> None:
    public_tokens = _count_public_tokens(changed, public_token_exclude_paths)
    verified_edges = _count_verified_edges(changed)
    if public_tokens > max_public_tokens:
        raise InvariantError(f"I6 fail: public_tokens={public_tokens} > {max_public_tokens}")
    if verified_edges < min_verified_edges:
        raise InvariantError(f"I6 fail: verified_edges={verified_edges} < {min_verified_edges}")


def _snapshot_hash_for(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        p = Path(path)
        if not p.exists() or p.is_dir():
            continue
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(p.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_runtime_ack(marker: Path, runtime_changed: list[str]) -> None:
    try:
        raw: object = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvariantError("I7 fail: runtime API acknowledgement is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise InvariantError("I7 fail: runtime API acknowledgement root must be an object")

    ack_id = raw.get("ack_id")
    reason = raw.get("reason")
    claim_status = raw.get("claim_status")
    surface = raw.get("runtime_surface")
    if not isinstance(ack_id, str) or not ack_id.strip():
        raise InvariantError("I7 fail: runtime API acknowledgement requires non-empty ack_id")
    if not isinstance(reason, str) or len(reason.strip()) < 24:
        raise InvariantError("I7 fail: runtime API acknowledgement requires substantive reason")
    if claim_status != "derived":
        raise InvariantError("I7 fail: runtime API acknowledgement must set claim_status='derived'")
    if not isinstance(surface, list) or not all(isinstance(item, str) for item in surface):
        raise InvariantError("I7 fail: runtime_surface must be a list of paths")

    missing = sorted(set(runtime_changed) - set(surface))
    if missing:
        raise InvariantError(
            "I7 fail: runtime API acknowledgement omits changed runtime files: "
            + ", ".join(missing)
        )


def _check_i7(
    changed: list[str],
    snapshot_file: str,
    runtime_risk_paths: list[str],
    hygiene_allowed_paths: list[str],
) -> None:
    runtime_changed = [p for p in changed if _is_allowed_path(p, runtime_risk_paths)]
    if not runtime_changed:
        return
    non_hygiene = [p for p in changed if not _is_allowed_path(p, hygiene_allowed_paths)]
    if not non_hygiene:
        raise InvariantError("I7 fail: runtime change hidden in hygiene-only PR")

    snap_path = Path(snapshot_file)
    if not snap_path.exists():
        raise InvariantError(f"I7 fail: missing snapshot file {snapshot_file}")
    expected = snap_path.read_text(encoding="utf-8").strip()
    actual = _snapshot_hash_for(runtime_changed)
    if expected == actual:
        return
    marker = Path(".repo/runtime_api_change_ack.json")
    if not marker.exists():
        raise InvariantError(
            "I7 fail: runtime API hash changed without "
            ".repo/runtime_api_change_ack.json"
        )
    _load_runtime_ack(marker, runtime_changed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=".repo/authorship_compiler.yaml")
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args()

    cfg = _load_config(Path(args.config))["invariants"]
    changed = _changed_files(args.base_ref)
    i6_cfg = cfg["i6_semantic_compression"]

    _check_i1(changed, cfg["i1_top_level_allowlist"]["allowed_top_level"])
    _check_i2(
        changed,
        cfg["i2_token_signature_regex"]["forbidden_patterns"],
        [args.config],
    )
    _check_i6(
        changed,
        i6_cfg["min_verified_edges"],
        i6_cfg["max_public_tokens"],
        i6_cfg.get("public_token_exclude_paths", []),
    )
    _check_i7(
        changed,
        cfg["i7_api_snapshot_hash_integrity"]["snapshot_file"],
        cfg["i7_api_snapshot_hash_integrity"]["runtime_risk_paths"],
        cfg["i7_api_snapshot_hash_integrity"]["hygiene_allowed_paths"],
    )

    print(json.dumps({"status": "ok", "changed_files": len(changed)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InvariantError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
