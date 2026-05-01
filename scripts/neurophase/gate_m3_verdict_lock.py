#!/usr/bin/env python3
"""Gate M3 — Programmatic verdict lock (NP-RUN1-GM3-v1.0).

Final gate. Assertion contract + explicit human CLI confirmation before
setting verdict_locked: true on RUN1_VERDICT.yaml.

Assertions:
  - RUN1_VERDICT.yaml exists and is NOT already locked.
  - results.H1_existence.result is one of the allowed verdict labels.
  - results.H2_utility.result is one of the allowed labels.
  - results.integration_ceiling.current_status is set.
  - results.input_artifact_hashes SHA-256s match current on-disk files.
  - LEDGER.yaml has successful 04, 05, 06, 07 entries.
  - No artifact_flag=True (if so, ceiling must be INVALID and operator
    must explicitly acknowledge).

On passing + operator CONFIRM → sets verdict_locked: true + provenance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from _common import (
    REPO_ROOT,
    append_ledger,
    freeze_file,
    load_config,
    parse_std_args,
    require_provenance_freeze,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_yaml,
)

H1_ALLOWED = {"CONFIRMED", "REJECTED", "INCONCLUSIVE", "INCONCLUSIVE_UNDERPOWERED"}
H2_ALLOWED = {"CONFIRMED", "CONFIRMED_WEAK", "REJECTED", "INCONCLUSIVE", "AMBIGUITY"}
CEILING_ALLOWED = {"EEG_TRACK_CLOSED", "WITNESS_ONLY", "WITNESS_PENDING",
                   "CANDIDATE_ADAPTER", "UNRESOLVED", "UNDERPOWERED_NULL", "INVALID"}


def _run_assertions(cfg: dict, log) -> tuple[bool, list[dict], dict]:
    results_dir = REPO_ROOT / cfg["paths"]["results_dir"]
    verdict_path = results_dir / "RUN1_VERDICT.yaml"
    ledger_path = REPO_ROOT / cfg["paths"]["ledger"]
    assertions: list[dict] = []

    def _check(name: str, passed: bool, detail: str) -> None:
        status = "PASS" if passed else "FAIL"
        assertions.append({"check": name, "status": status, "detail": detail})
        log.log(20 if passed else 40, f"assertion {status}: {name} — {detail}")

    _check("RUN1_VERDICT.yaml exists", verdict_path.exists(), str(verdict_path))
    if not verdict_path.exists():
        return False, assertions, {}
    verdict = yaml.safe_load(verdict_path.read_text()) or {}
    _check("verdict_locked is False (not already locked)",
           verdict.get("verdict_locked", False) is False,
           f"value={verdict.get('verdict_locked')}")

    r = verdict.get("results", {}) or {}
    h1_result = (r.get("H1_existence") or {}).get("result")
    h2_result = (r.get("H2_utility") or {}).get("result")
    ceiling = (r.get("integration_ceiling") or {}).get("current_status")
    _check("H1 result is a recognized label", h1_result in H1_ALLOWED, f"h1={h1_result}")
    _check("H2 result is a recognized label", h2_result in H2_ALLOWED, f"h2={h2_result}")
    _check("integration_ceiling.current_status is set", ceiling in CEILING_ALLOWED,
           f"ceiling={ceiling}")

    # Verify input report hashes still match disk
    iah = r.get("input_artifact_hashes") or {}
    for key in ("existence_report", "utility_report", "robustness_report"):
        entry = iah.get(key) or {}
        p = Path(entry.get("path", ""))
        if not p.exists():
            _check(f"{key} present on disk", False, f"missing {p}")
            continue
        cur = sha256_file(p)
        _check(f"{key} SHA-256 stable since write_verdict",
               cur == entry.get("sha256"),
               f"disk={cur[:12]}… vs recorded={(entry.get('sha256') or '')[:12]}…")

    # Ledger must have 04, 05, 06, 07 ok entries
    ledger = yaml.safe_load(ledger_path.read_text()) if ledger_path.exists() else []
    stages = [(e.get("stage"), e.get("status")) for e in ledger if isinstance(e, dict)]
    for stage_name in ("04_existence_test", "05_utility_test",
                       "06_robustness", "07_write_verdict"):
        _check(f"LEDGER has {stage_name} ok",
               (stage_name, "ok") in stages,
               f"recent_stages={stages[-6:]}")

    # Artifact gate
    rob = r.get("robustness") or {}
    artifact = rob.get("artifact_flag")
    _check("artifact_flag is not True, or ceiling is INVALID",
           (artifact is not True) or ceiling == "INVALID",
           f"artifact_flag={artifact}, ceiling={ceiling}")

    all_passed = all(a["status"] == "PASS" for a in assertions)
    return all_passed, assertions, verdict


def main() -> None:
    ap = argparse.ArgumentParser(prog="neurophase.gate_m3_verdict_lock")
    ap.add_argument("--config", default=str(REPO_ROOT / "config" / "neurophase_run1.yaml"))
    ap.add_argument("--auto_confirm", action="store_true")
    ap.add_argument("--operator", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    _ = require_provenance_freeze(cfg)
    log = setup_logging("gate_m3_verdict_lock", cfg)
    log.info("=" * 72)
    log.info("Gate M3 — verdict lock (programmatic)")
    log.info("=" * 72)

    passed, assertions, verdict = _run_assertions(cfg, log)
    if not passed:
        log.critical("assertion contract FAILED — CONFIRM prompt suppressed")
        append_ledger(cfg, {"stage": "gate_m3_verdict_lock", "status": "HALT",
                            "reason": "assertion_contract_failed",
                            "assertions": assertions})
        sys.exit(3)

    r = verdict["results"]
    log.info(f"about to lock verdict for {verdict.get('run_id')}:")
    log.info(f"    H1 = {(r.get('H1_existence') or {}).get('result')}")
    log.info(f"    H2 = {(r.get('H2_utility') or {}).get('result')}")
    log.info(f"    ceiling = {(r.get('integration_ceiling') or {}).get('current_status')}")
    log.info(f"    next_action = {r.get('next_action')}")

    if args.auto_confirm:
        confirmation = "AUTO_CONFIRM"
        log.warning("--auto_confirm used — human prompt bypassed; logged in LEDGER")
    else:
        print("\n--- CONFIRM VERDICT LOCK ---")
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
            append_ledger(cfg, {"stage": "gate_m3_verdict_lock", "status": "aborted",
                                "reason": "confirm_not_entered"})
            sys.exit(3)
        confirmation = "CONFIRM"

    verdict["verdict_locked"] = True
    verdict["verdict_lock_timestamp"] = utc_now_iso()
    verdict["verdict_lock_operator"] = args.operator or "auto"
    verdict["verdict_lock_confirmation"] = confirmation
    verdict_path = REPO_ROOT / cfg["paths"]["results_dir"] / "RUN1_VERDICT.yaml"
    write_yaml(verdict_path, verdict)
    frozen_sha = freeze_file(verdict_path)
    append_ledger(cfg, {"stage": "gate_m3_verdict_lock", "status": "ok",
                        "assertions": assertions,
                        "confirmation": confirmation,
                        "operator": args.operator or "auto",
                        "verdict_sha256_post_lock": frozen_sha,
                        "h1_final": (verdict["results"].get("H1_existence") or {}).get("result"),
                        "h2_final": (verdict["results"].get("H2_utility") or {}).get("result"),
                        "ceiling_final": (verdict["results"].get("integration_ceiling") or {}).get("current_status")})
    log.info(f"verdict_locked: true written + file frozen (sha256={frozen_sha[:16]}…)")
    log.info("END OF RUN 1.")


if __name__ == "__main__":
    main()
