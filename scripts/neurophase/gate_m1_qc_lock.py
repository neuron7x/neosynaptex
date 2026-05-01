#!/usr/bin/env python3
"""Gate M1 — Programmatic QC lock (NP-RUN1-GM1-v1.0).

Replaces the manual 'set analyst_lock: true' step with a programmatic
assertion contract + explicit human CLI confirmation.

Flow:
  1. Load QC_SUMMARY.yaml + PROVENANCE_FREEZE.yaml + LEDGER.yaml.
  2. Run assertion contract — all MUST pass or the script exits without
     prompting; no CONFIRM is possible if invariants are violated.
  3. Display a diff-style summary of what will be locked.
  4. Prompt the operator to type 'CONFIRM' on stdin (exact match).
     --auto_confirm bypasses the prompt for CI/self-test (logged in LEDGER).
  5. Set analyst_lock: true with timestamp and confirmation provenance.

This does NOT compute QC decisions; those were frozen in Stage 02. This
gate only verifies the invariants and records the human decision to
proceed, turning the manual step into a signed, auditable action.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from _common import (
    REPO_ROOT,
    append_ledger,
    load_config,
    load_contract,
    require_provenance_freeze,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_yaml,
)


def _run_assertions(cfg: dict, log) -> tuple[bool, list[dict], dict]:
    """Returns (all_passed, assertion_records, summary)."""
    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    summary_path = qc_dir / "QC_SUMMARY.yaml"
    excluded_path = qc_dir / "EXCLUDED_SUBJECTS.yaml"
    pf_path = qc_dir / "PROVENANCE_FREEZE.yaml"
    ledger_path = REPO_ROOT / cfg["paths"]["ledger"]

    assertions: list[dict] = []

    def _check(name: str, passed: bool, detail: str) -> None:
        status = "PASS" if passed else "FAIL"
        rec = {"check": name, "status": status, "detail": detail}
        assertions.append(rec)
        log.log(20 if passed else 40, f"assertion {status}: {name} — {detail}")

    ok_files = True
    for p, label in [(summary_path, "QC_SUMMARY.yaml"),
                     (excluded_path, "EXCLUDED_SUBJECTS.yaml"),
                     (pf_path, "PROVENANCE_FREEZE.yaml"),
                     (ledger_path, "LEDGER.yaml")]:
        exists = p.exists()
        _check(f"{label} present", exists, str(p))
        ok_files &= exists
    if not ok_files:
        return False, assertions, {}

    summary = yaml.safe_load(summary_path.read_text()) or {}
    pf = yaml.safe_load(pf_path.read_text()) or {}
    ledger = yaml.safe_load(ledger_path.read_text()) or []

    # Contract hash must match across summary and provenance freeze
    contract = load_contract(cfg)
    current_sha = contract["_contract_sha256"]
    _check("contract hash matches PROVENANCE_FREEZE",
           pf.get("contract_sha256") == current_sha,
           f"pf={pf.get('contract_sha256', '?')[:12]}… vs current={current_sha[:12]}…")
    _check("contract hash matches QC_SUMMARY",
           summary.get("contract_sha256") == current_sha,
           f"summary={summary.get('contract_sha256', '?')[:12]}… vs current={current_sha[:12]}…")
    _check("provenance_lock: true", pf.get("provenance_lock", False) is True,
           f"value={pf.get('provenance_lock')}")
    _check("analyst_lock still False (not already set)",
           summary.get("analyst_lock", False) is False,
           f"value={summary.get('analyst_lock')}")

    # Ledger must contain successful 01 + 02 entries
    stages = [(e.get("stage"), e.get("status")) for e in ledger if isinstance(e, dict)]
    _check("LEDGER has 01_ingest_bids ok", ("01_ingest_bids", "ok") in stages,
           f"stages={stages[-5:]}")
    _check("LEDGER has 02_qc ok", ("02_qc", "ok") in stages,
           f"stages={stages[-5:]}")

    # Cohort invariants
    n_ingested_ok = int(summary.get("n_subjects_ingested_ok", 0))
    n_final = int(summary.get("n_subjects_candidate_for_preprocessing", 0))
    drop = n_ingested_ok - n_final
    drop_frac = (drop / n_ingested_ok) if n_ingested_ok else 1.0
    _check("QC exclusion fraction ≤ 0.30", drop_frac <= 0.30,
           f"drop={drop}/{n_ingested_ok} = {drop_frac:.3f}")
    _check("at least 1 subject candidate for preprocessing", n_final >= 1,
           f"n_candidate={n_final}")

    all_passed = all(a["status"] == "PASS" for a in assertions)
    return all_passed, assertions, summary


def main() -> None:
    ap = argparse.ArgumentParser(prog="neurophase.gate_m1_qc_lock")
    ap.add_argument("--config", default=str(REPO_ROOT / "config" / "neurophase_run1.yaml"))
    ap.add_argument("--auto_confirm", action="store_true",
                    help="bypass CONFIRM prompt (logs override in LEDGER)")
    ap.add_argument("--operator", default=None, help="operator identifier for audit (optional)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    _ = require_provenance_freeze(cfg)
    log = setup_logging("gate_m1_qc_lock", cfg)
    log.info("=" * 72)
    log.info("Gate M1 — QC lock (programmatic)")
    log.info("=" * 72)

    passed, assertions, summary = _run_assertions(cfg, log)
    if not passed:
        log.critical("assertion contract FAILED — CONFIRM prompt suppressed")
        append_ledger(cfg, {"stage": "gate_m1_qc_lock", "status": "HALT",
                            "reason": "assertion_contract_failed",
                            "assertions": assertions})
        sys.exit(3)

    log.info("all assertions PASSED. Summary to be locked:")
    for k in ("run_id", "n_subjects_ingested_ok", "n_excluded_behavioral",
              "n_excluded_channel", "n_excluded_epoch_preview",
              "n_subjects_candidate_for_preprocessing", "qc_completion_timestamp"):
        if k in summary:
            log.info(f"    {k}: {summary[k]}")

    if args.auto_confirm:
        confirmation = "AUTO_CONFIRM"
        log.warning("--auto_confirm used — human prompt bypassed; logged in LEDGER")
    else:
        print("\n--- CONFIRM QC LOCK ---")
        print("Type 'CONFIRM' to set analyst_lock: true (anything else aborts).")
        print("Operator identifier (optional): "
              f"{args.operator or '(prompted)'}")
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
            log.critical(f"operator typed {reply!r} — aborting without lock.")
            append_ledger(cfg, {"stage": "gate_m1_qc_lock", "status": "aborted",
                                "reason": "confirm_not_entered",
                                "operator": args.operator})
            sys.exit(3)
        confirmation = "CONFIRM"

    summary["analyst_lock"] = True
    summary["analyst_lock_timestamp"] = utc_now_iso()
    summary["analyst_lock_operator"] = args.operator or "auto"
    summary["analyst_lock_confirmation"] = confirmation
    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    summary_path = qc_dir / "QC_SUMMARY.yaml"
    write_yaml(summary_path, summary)

    append_ledger(cfg, {"stage": "gate_m1_qc_lock", "status": "ok",
                        "assertions": assertions,
                        "confirmation": confirmation,
                        "operator": args.operator or "auto",
                        "qc_summary_sha256": sha256_file(summary_path)})
    log.info(f"analyst_lock: true written to {summary_path}")


if __name__ == "__main__":
    main()
