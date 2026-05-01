#!/usr/bin/env python3
"""Gate M2 — Programmatic feature-store freeze (NP-RUN1-GM2-v1.0).

Replaces the manual 'chmod -R a-w features/' + hash-verify step with an
auditable assertion contract + explicit human CLI confirmation.

Flow:
  1. Load FEATURE_STORE_MANIFEST.json + verify every listed file's SHA-256
     still matches the manifest entry (catches corruption / tampering).
  2. Verify every file in features/ is accounted for (no stragglers).
  3. Display what will be frozen (file count, total size, hash digest).
  4. Prompt 'CONFIRM' on stdin (exact match). --auto_confirm for CI.
  5. chmod -R a-w features/ and FEATURE_STORE_MANIFEST.json.
  6. Append LEDGER entry with operator + confirmation record.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import (
    REPO_ROOT,
    append_ledger,
    freeze_file,
    is_frozen,
    load_config,
    load_qc_summary,
    require_provenance_freeze,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_json,
)


def _run_assertions(cfg: dict, log) -> tuple[bool, list[dict], dict]:
    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    manifest_path = features_dir / "FEATURE_STORE_MANIFEST.json"
    assertions: list[dict] = []

    def _check(name: str, passed: bool, detail: str) -> None:
        status = "PASS" if passed else "FAIL"
        assertions.append({"check": name, "status": status, "detail": detail})
        log.log(20 if passed else 40, f"assertion {status}: {name} — {detail}")

    _check("features_dir exists", features_dir.exists(), str(features_dir))
    _check("FEATURE_STORE_MANIFEST.json exists", manifest_path.exists(), str(manifest_path))
    if not manifest_path.exists():
        return False, assertions, {}

    manifest = json.loads(manifest_path.read_text())
    listed = {Path(s["file"]).resolve(): s for s in manifest["subjects"]}

    existing = {p.resolve() for p in features_dir.glob("*_features.h5")}
    unknown_files = existing - set(listed.keys())
    missing_files = set(listed.keys()) - existing
    _check("no untracked *_features.h5 files", not unknown_files,
           f"unknown={list(map(str, unknown_files))[:3]}")
    _check("no manifest entries missing on disk", not missing_files,
           f"missing={list(map(str, missing_files))[:3]}")

    recomputed = []
    for path, entry in listed.items():
        actual = sha256_file(path)
        match = actual == entry["sha256"]
        recomputed.append({"subject_id": entry["subject_id"], "match": match,
                           "expected": entry["sha256"], "actual": actual})
        _check(f"hash match for {entry['subject_id']}", match,
               f"{actual[:12]}… vs {entry['sha256'][:12]}…")

    return all(a["status"] == "PASS" for a in assertions), assertions, manifest


def main() -> None:
    ap = argparse.ArgumentParser(prog="neurophase.gate_m2_freeze_features")
    ap.add_argument("--config", default=str(REPO_ROOT / "config" / "neurophase_run1.yaml"))
    ap.add_argument("--auto_confirm", action="store_true")
    ap.add_argument("--operator", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("gate_m2_freeze_features", cfg)
    log.info("=" * 72)
    log.info("Gate M2 — feature-store freeze (programmatic)")
    log.info("=" * 72)

    passed, assertions, manifest = _run_assertions(cfg, log)
    if not passed:
        log.critical("assertion contract FAILED — CONFIRM prompt suppressed")
        append_ledger(cfg, {"stage": "gate_m2_freeze_features", "status": "HALT",
                            "reason": "assertion_contract_failed",
                            "assertions": assertions})
        sys.exit(3)

    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    h5_files = sorted(features_dir.glob("*_features.h5"))
    already_frozen = all(is_frozen(p) for p in h5_files)
    if already_frozen:
        log.warning("all feature files are already frozen (read-only); nothing to do.")
    total_size = sum(p.stat().st_size for p in h5_files)
    log.info(f"about to freeze {len(h5_files)} files, total {total_size/1e6:.1f} MB")
    log.info(f"manifest_sha256 = {sha256_file(features_dir / 'FEATURE_STORE_MANIFEST.json')[:16]}…")

    if args.auto_confirm:
        confirmation = "AUTO_CONFIRM"
        log.warning("--auto_confirm used — human prompt bypassed; logged in LEDGER")
    else:
        print("\n--- CONFIRM FEATURE STORE FREEZE ---")
        if not args.operator:
            try:
                args.operator = input("operator: ").strip() or "anonymous"
            except EOFError:
                log.critical("EOF on stdin; aborting.")
                sys.exit(3)
        try:
            reply = input("CONFIRM: ").strip()
        except EOFError:
            log.critical("EOF on stdin; aborting.")
            sys.exit(3)
        if reply != "CONFIRM":
            log.critical(f"operator typed {reply!r} — aborting.")
            append_ledger(cfg, {"stage": "gate_m2_freeze_features", "status": "aborted",
                                "reason": "confirm_not_entered"})
            sys.exit(3)
        confirmation = "CONFIRM"

    frozen = {}
    for p in h5_files:
        h = freeze_file(p)
        frozen[p.name] = h
    manifest_p = features_dir / "FEATURE_STORE_MANIFEST.json"
    mh = freeze_file(manifest_p)
    append_ledger(cfg, {"stage": "gate_m2_freeze_features", "status": "ok",
                        "assertions": assertions,
                        "confirmation": confirmation,
                        "operator": args.operator or "auto",
                        "manifest_sha256_post_freeze": mh,
                        "n_frozen": len(frozen)})
    log.info(f"freeze complete: {len(frozen)} feature files + manifest now read-only.")


if __name__ == "__main__":
    main()
