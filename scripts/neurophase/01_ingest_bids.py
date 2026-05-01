#!/usr/bin/env python3
"""Stage 01 — BIDS Ingestion + Provenance Freeze (NP-RUN1-S01-v1.1).

Contract:
  1. Read-only. No modification to raw data.
  2. Validates root-level BIDS invariants (dataset_description.json,
     participants.tsv, task-pst_eeg.json, BIDSVersion ≥ 1.2.0).
  3. Per-subject provenance capture:
       - File presence (.set/.fdt/events.tsv/channels.tsv)
       - SHA-256 of .set + events.tsv + channels.tsv (not .fdt — too large)
       - channels.tsv audit (EOG rule table, interpolation rule table)
       - events.tsv audit (mandatory columns, event count sanity)
  4. Resume: if an existing ingestion_manifest.json is NOT frozen, subjects
     are reused from the checkpoint. Frozen manifests HALT — manual unlock
     is required for re-ingestion.
  5. Writes ingestion_manifest.json + freezes it (chmod a-w + sidecar .freeze).
  6. Writes PROVENANCE_FREEZE.yaml — the immutable audit artifact that ALL
     downstream stages require (enforced by _common.require_provenance_freeze).

Rule tables (deterministic, no heuristic branching):
  EOG-R01 — no EOG-typed channels → Fp1/Fp2 proxy required
  EOG-R02 — > 4 EOG-typed channels → possible mislabeling
  EOG-R03 — channel named 'EOG*' but typed EEG → type-field mismatch
  INTERP-R01 — any pre-interpolated channel → flag
  INTERP-R02 — > 5 pre-interpolated channels → variance-independence risk
"""
from __future__ import annotations

import csv
import fnmatch
import json
import re
import sys
from collections import Counter
from pathlib import Path

from _common import (
    REPO_ROOT,
    SEV_FLAG,
    SEV_WARN,
    append_ledger,
    evaluate_rules,
    freeze_file,
    is_frozen,
    load_config,
    load_contract,
    parse_std_args,
    set_global_seed,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_json,
    write_yaml,
    write_ledger_halt,
)

SUB_DIR_RE = re.compile(r"^sub-\d+$")
REQUIRED_ROOT_FILES = ["dataset_description.json", "participants.tsv", "task-pst_eeg.json"]
TASK_LABEL = "pst"
INTERP_TOKENS = ("interp",)

EOG_AUDIT_RULES = [
    {"rule_id": "EOG-R01", "description": "No EOG-typed channels — Fp1/Fp2 proxy required",
     "severity": SEV_FLAG, "detail_key": "n_eog_typed", "threshold": 0, "operator": "eq"},
    {"rule_id": "EOG-R02", "description": "> 4 EOG-typed channels — possible mislabeling",
     "severity": SEV_WARN, "detail_key": "n_eog_typed", "threshold": 4, "operator": "gt"},
    {"rule_id": "EOG-R03", "description": "Channel named EOG* but typed EEG — type-field mismatch",
     "severity": SEV_FLAG, "detail_key": "eog_name_eeg_type", "threshold": 0, "operator": "gt"},
]

INTERP_AUDIT_RULES = [
    {"rule_id": "INTERP-R01", "description": "Pre-interpolated channels detected",
     "severity": SEV_FLAG, "detail_key": "n_interpolated", "threshold": 0, "operator": "gt"},
    {"rule_id": "INTERP-R02", "description": "> 5 pre-interpolated channels — variance-independence risk",
     "severity": SEV_WARN, "detail_key": "n_interpolated", "threshold": 5, "operator": "gt"},
]


def _find_files(eeg_dir: Path, pattern: str) -> list[Path]:
    return sorted(p for p in eeg_dir.iterdir() if fnmatch.fnmatch(p.name, pattern))


def _validate_root(bids_root: Path, contract: dict, log) -> dict:
    violations = []
    for fname in REQUIRED_ROOT_FILES:
        if not (bids_root / fname).exists():
            violations.append(f"missing root file: {fname}")
    if violations:
        log.error("root validation failed: " + "; ".join(violations))
        return {"status": "HALT", "violations": violations}

    desc = json.loads((bids_root / "dataset_description.json").read_text())
    bids_ver = desc.get("BIDSVersion", "0.0.0")
    if bids_ver < contract["dataset"]["bids_version_min"]:
        return {"status": "HALT", "violations": [f"BIDSVersion {bids_ver} < required {contract['dataset']['bids_version_min']}"]}

    pts_path = bids_root / "participants.tsv"
    with pts_path.open() as f:
        n_participants = sum(1 for _ in csv.DictReader(f, delimiter="\t"))

    return {
        "status": "ok",
        "dataset_name": desc.get("Name", "unknown"),
        "bids_version": bids_ver,
        "n_participants_tsv": n_participants,
        "root_hashes": {
            "dataset_description.json": sha256_file(bids_root / "dataset_description.json"),
            "participants.tsv": sha256_file(pts_path),
            "task-pst_eeg.json": sha256_file(bids_root / "task-pst_eeg.json"),
        },
    }


def _audit_channels(path: Path, log, sub_id: str) -> dict:
    with path.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    type_dist = Counter(r.get("type", "MISSING") for r in rows)
    eog_typed = [r for r in rows if r.get("type", "").upper() in ("EOG", "VEOG", "HEOG")]
    eog_name_eeg_type = [r for r in rows if "EOG" in r.get("name", "").upper()
                         and r.get("type", "").upper() == "EEG"]
    interp_rows = [r for r in rows if any(tok in (r.get(f) or "").lower()
                   for tok in INTERP_TOKENS for f in ("status", "status_description", "notes"))]
    bad_upstream = [r.get("name") for r in rows
                    if "bad" in (r.get("status") or "").lower() or "bad" in (r.get("status_description") or "").lower()]

    eog_values = {"n_eog_typed": len(eog_typed), "eog_name_eeg_type": len(eog_name_eeg_type)}
    interp_values = {"n_interpolated": len(interp_rows)}

    eog_fired = evaluate_rules(EOG_AUDIT_RULES, eog_values, log, sub_id)
    interp_fired = evaluate_rules(INTERP_AUDIT_RULES, interp_values, log, sub_id)

    fp_present = any(r.get("name") in ("Fp1", "Fp2") for r in rows)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "n_channels": len(rows),
        "type_distribution": dict(type_dist),
        "eog_channels": [r.get("name") for r in eog_typed],
        "n_eog_typed": len(eog_typed),
        "eog_name_eeg_type": [r.get("name") for r in eog_name_eeg_type],
        "interpolated_channels": [r.get("name") for r in interp_rows],
        "n_interpolated": len(interp_rows),
        "bad_channels_upstream": bad_upstream,
        "needs_fp1fp2_proxy": (len(eog_typed) == 0 and fp_present),
        "eog_rules_fired": eog_fired,
        "interp_rules_fired": interp_fired,
    }


def _audit_events(path: Path, mandatory: list[str]) -> dict:
    with path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        cols = reader.fieldnames or []
        rows = list(reader)
    missing = [c for c in mandatory if c not in cols]
    miss_frac: dict[str, float] = {}
    if not missing:
        for c in mandatory:
            vals = [r.get(c, "") for r in rows]
            miss_frac[c] = round(sum(1 for v in vals if v in ("", "n/a", "NA", None)) / max(1, len(vals)), 4)
    over_10 = [c for c, f in miss_frac.items() if f > 0.10]
    n_ev = len(rows)
    count_anomaly = n_ev < 200 or n_ev > 800
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "n_rows": n_ev,
        "columns_seen": cols,
        "mandatory_missing": missing,
        "missing_fraction_per_column": miss_frac,
        "over_10pct_missing": over_10,
        "count_anomaly": count_anomaly,
    }


def _ingest_subject(sub_dir: Path, sub_id: str, cfg: dict, log) -> dict:
    record = {
        "subject_id": sub_id,
        "eeg_set_path": None,
        "eeg_fdt_path": None,
        "events_path": None,
        "channels_path": None,
        "electrodes_path": None,
        "eeg_set_sha256": None,
        "events_sha256": None,
        "channels_sha256": None,
        "fdt_size_bytes": None,
        "size_anomaly": False,
        "status": "ok",
        "exclusion_reason": None,
        "flags": [],
        "ingestion_timestamp": utc_now_iso(),
        "channels_audit": None,
        "events_audit": None,
    }
    eeg_dir = sub_dir / "eeg"
    if not eeg_dir.exists():
        record["status"] = "missing_eeg_dir"
        record["exclusion_reason"] = "eeg/ absent"
        log.warning(f"{sub_id}: eeg/ absent → excluded")
        return record

    set_f = _find_files(eeg_dir, f"*_task-{TASK_LABEL}_eeg.set")
    fdt_f = _find_files(eeg_dir, f"*_task-{TASK_LABEL}_eeg.fdt")
    ev_f = _find_files(eeg_dir, f"*_task-{TASK_LABEL}_events.tsv")
    ch_f = _find_files(eeg_dir, f"*_task-{TASK_LABEL}_channels.tsv")
    el_f = _find_files(eeg_dir, f"*_task-{TASK_LABEL}_electrodes.tsv")

    # .fdt is optional: EEGLAB .set can be either paired (.set+.fdt) or
    # single-file (data inside .set). MNE handles both. We flag but don't
    # exclude based on .fdt absence.
    missing = [n for n, lst in [("set", set_f), ("events", ev_f), ("channels", ch_f)] if not lst]
    if missing:
        record["status"] = "missing_files"
        record["exclusion_reason"] = f"missing: {missing}"
        log.warning(f"{sub_id}: {record['exclusion_reason']} → excluded")
        return record

    record["eeg_set_path"] = str(set_f[0].resolve())
    record["eeg_fdt_path"] = str(fdt_f[0].resolve()) if fdt_f else None
    record["events_path"] = str(ev_f[0].resolve())
    record["channels_path"] = str(ch_f[0].resolve())
    if el_f:
        record["electrodes_path"] = str(el_f[0].resolve())
    record["is_paired_set_fdt"] = bool(fdt_f)

    # Size: prefer .fdt if paired (binary data), else .set total size
    fdt_size = fdt_f[0].stat().st_size if fdt_f else set_f[0].stat().st_size
    record["fdt_size_bytes"] = fdt_size
    sz_min = int(cfg["eeg_size_bounds_bytes"]["min"])
    sz_max = int(cfg["eeg_size_bounds_bytes"]["max"])
    if fdt_size < sz_min or fdt_size > sz_max:
        record["size_anomaly"] = True
        record["flags"].append(f"fdt_size={fdt_size} outside [{sz_min}, {sz_max}]")

    record["eeg_set_sha256"] = sha256_file(set_f[0])
    record["events_sha256"] = sha256_file(ev_f[0])
    record["channels_sha256"] = sha256_file(ch_f[0])
    record["channels_audit"] = _audit_channels(ch_f[0], log, sub_id)
    record["events_audit"] = _audit_events(ev_f[0], cfg["events_mandatory_columns"])

    if record["events_audit"]["mandatory_missing"]:
        record["status"] = "events_missing_mandatory"
        record["exclusion_reason"] = f"events.tsv missing {record['events_audit']['mandatory_missing']}"
    elif record["events_audit"]["over_10pct_missing"]:
        record["flags"].append(f"events >10% missing in {record['events_audit']['over_10pct_missing']}")
    if record["events_audit"]["count_anomaly"]:
        record["flags"].append(f"event_count={record['events_audit']['n_rows']} outside [200,800]")

    log.info(f"{sub_id}: {record['status']} | fdt={fdt_size/1e6:.1f}MB | "
             f"ch={record['channels_audit']['n_channels']} | ev={record['events_audit']['n_rows']} | "
             f"eog_typed={record['channels_audit']['n_eog_typed']} | "
             f"interp_upstream={record['channels_audit']['n_interpolated']}")
    return record


def main() -> None:
    args = parse_std_args("01_ingest_bids")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    log = setup_logging("01_ingest_bids", cfg)

    bids_root = Path(args.bids_root) if args.bids_root else (REPO_ROOT / cfg["paths"]["bids_root"])
    bids_root = bids_root.resolve()
    log.info("=" * 72)
    log.info(f"Stage 01 — BIDS ingestion | run_id={cfg['run_id']}")
    log.info(f"bids_root : {bids_root}")
    log.info(f"contract  : {contract['_contract_path']} sha256={contract['_contract_sha256'][:12]}…")
    log.info("=" * 72)

    if not bids_root.exists():
        log.critical(f"bids_root not found: {bids_root}")
        sys.exit(f"[FAIL-CLOSED] BIDS root not found: {bids_root}\n"
                 f"    Acquire ds003474 v{contract['dataset']['version']} from "
                 f"{contract['dataset']['url']} and place at path, or pass --bids_root.")

    root = _validate_root(bids_root, contract, log)
    if root["status"] == "HALT":
        write_ledger_halt(cfg, "01_ingest_bids", "root_validation_failed", root)
        sys.exit(2)
    log.info(f"Root: {root['dataset_name']} | BIDS {root['bids_version']} | "
             f"participants.tsv rows={root['n_participants_tsv']}")

    sub_dirs = sorted([d for d in bids_root.iterdir() if d.is_dir() and SUB_DIR_RE.match(d.name)])
    log.info(f"Discovered {len(sub_dirs)} subject directories.")
    if abs(len(sub_dirs) - root["n_participants_tsv"]) > 2:
        detail = {"n_dirs": len(sub_dirs), "n_participants_tsv": root["n_participants_tsv"]}
        log.critical(f"subject count mismatch > 2: {detail}")
        write_ledger_halt(cfg, "01_ingest_bids", "subject_count_mismatch", detail)
        sys.exit(2)

    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    qc_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = qc_dir / "ingestion_manifest.json"
    freeze_path = qc_dir / "ingestion_manifest.freeze"

    checkpoint: dict[str, dict] = {}
    if manifest_path.exists():
        if is_frozen(manifest_path):
            log.critical(f"existing manifest is FROZEN; re-ingestion blocked: {manifest_path}")
            write_ledger_halt(cfg, "01_ingest_bids", "frozen_manifest_conflict",
                              {"manifest": str(manifest_path)})
            sys.exit(2)
        try:
            prev = json.loads(manifest_path.read_text())
            checkpoint = {r["subject_id"]: r for r in prev.get("subjects", [])}
            log.info(f"RESUME: loaded {len(checkpoint)} records from existing manifest.")
        except Exception as e:
            log.warning(f"could not parse existing manifest ({e}); starting fresh.")

    records: list[dict] = []
    n_ok = n_excl = n_flag = n_resume = 0
    for sd in sub_dirs:
        sid = sd.name
        if sid in checkpoint and checkpoint[sid].get("status") == "ok":
            rec = checkpoint[sid]
            n_resume += 1
            log.info(f"{sid}: RESUMED from checkpoint")
        else:
            rec = _ingest_subject(sd, sid, cfg, log)
        records.append(rec)
        if rec["status"] == "ok":
            n_ok += 1
        elif rec["status"] in ("missing_files", "missing_eeg_dir"):
            n_excl += 1
        else:
            n_flag += 1

    log.info(f"Ingestion: {n_ok} OK | {n_excl} excluded | {n_flag} flagged | {n_resume} resumed")

    if args.dry_run:
        log.info("DRY RUN — no output files written.")
        return

    manifest = {
        "run_id": cfg["run_id"],
        "stage": "01_ingest_bids",
        "contract_sha256": contract["_contract_sha256"],
        "config_sha256": cfg["_config_sha256"],
        "timestamp": utc_now_iso(),
        "bids_root": str(bids_root),
        "dataset_name": root["dataset_name"],
        "bids_version": root["bids_version"],
        "root_hashes": root["root_hashes"],
        "n_subjects_discovered": len(sub_dirs),
        "n_ok": n_ok, "n_excluded": n_excl, "n_flagged": n_flag, "n_resumed": n_resume,
        "manifest_frozen": False,
        "subjects": records,
    }
    write_json(manifest_path, manifest)
    manifest_sha = freeze_file(manifest_path)
    write_json(freeze_path, {
        "manifest_path": str(manifest_path), "sha256": manifest_sha,
        "frozen_at": utc_now_iso(), "n_subjects": len(records),
        "n_ok": n_ok, "n_excluded": n_excl, "n_flagged": n_flag,
    })
    freeze_file(freeze_path)
    log.info(f"Manifest frozen: {manifest_path} sha256={manifest_sha[:12]}…")

    index_path = qc_dir / "subject_index.csv"
    fieldnames = ["subject_id", "status", "exclusion_reason", "fdt_size_bytes",
                  "size_anomaly", "eeg_set_sha256", "ingestion_timestamp"]
    with index_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)

    excluded = [{"subject_id": r["subject_id"], "reason": r["exclusion_reason"]}
                for r in records if r["status"] in ("missing_files", "missing_eeg_dir")]
    flagged = [{"subject_id": r["subject_id"], "status": r["status"], "flags": r.get("flags", [])}
               for r in records if r["flags"] or r["status"] not in ("ok", "missing_files", "missing_eeg_dir")]
    excl_path = qc_dir / "EXCLUDED_SUBJECTS.yaml"
    write_yaml(excl_path, {"stage": "01_ingest_bids", "timestamp": utc_now_iso(),
                           "ingestion_exclusions": excluded, "flagged_for_review": flagged})

    channel_prov = {r["subject_id"]: r["channels_audit"] for r in records if r["channels_audit"]}
    events_prov = {r["subject_id"]: r["events_audit"] for r in records if r["events_audit"]}
    ch_prov_path = qc_dir / "channel_provenance.json"
    ev_prov_path = qc_dir / "events_provenance.json"
    write_json(ch_prov_path, channel_prov)
    write_json(ev_prov_path, events_prov)

    n_eog_flag = sum(1 for v in channel_prov.values() if v.get("eog_rules_fired"))
    n_interp_flag = sum(1 for v in channel_prov.values() if v.get("interp_rules_fired"))
    n_bad_upstream = sum(1 for v in channel_prov.values() if v.get("bad_channels_upstream"))

    provenance_freeze = {
        "run_id": cfg["run_id"],
        "contract_sha256": contract["_contract_sha256"],
        "config_sha256": cfg["_config_sha256"],
        "dataset": {
            "openneuro_accession": contract["dataset"]["openneuro_accession"],
            "version_required": contract["dataset"]["version"],
            "bids_version_seen": root["bids_version"],
            "bids_version_min": contract["dataset"]["bids_version_min"],
            "root_hashes": root["root_hashes"],
        },
        "ingestion": {
            "n_subjects_dirs": len(sub_dirs),
            "n_subjects_participants": root["n_participants_tsv"],
            "n_ingestion_ok": n_ok,
            "n_ingestion_excluded": n_excl,
            "n_ingestion_flagged": n_flag,
        },
        "provenance_risks": {
            "n_subjects_with_eog_rule_fired": n_eog_flag,
            "n_subjects_with_interp_rule_fired": n_interp_flag,
            "n_subjects_with_bad_channels_upstream": n_bad_upstream,
        },
        "provenance_artifacts": {
            "ingestion_manifest": {"path": str(manifest_path), "sha256": manifest_sha},
            "subject_index": {"path": str(index_path), "sha256": sha256_file(index_path)},
            "channel_provenance": {"path": str(ch_prov_path), "sha256": sha256_file(ch_prov_path)},
            "events_provenance": {"path": str(ev_prov_path), "sha256": sha256_file(ev_prov_path)},
            "excluded_subjects": {"path": str(excl_path), "sha256": sha256_file(excl_path)},
        },
        "frozen_at": utc_now_iso(),
        "provenance_lock": True,
    }
    pf_path = qc_dir / "PROVENANCE_FREEZE.yaml"
    write_yaml(pf_path, provenance_freeze)
    log.info(f"Provenance freeze written: {pf_path}")

    append_ledger(cfg, {
        "stage": "01_ingest_bids",
        "input": {"bids_root": str(bids_root),
                  "contract_sha256": contract["_contract_sha256"],
                  "config_sha256": cfg["_config_sha256"]},
        "output": {
            "manifest": str(manifest_path), "manifest_sha256": manifest_sha,
            "provenance_freeze": str(pf_path), "provenance_freeze_sha256": sha256_file(pf_path),
            "channel_provenance_sha256": sha256_file(ch_prov_path),
            "events_provenance_sha256": sha256_file(ev_prov_path),
            "n_ok": n_ok, "n_excluded": n_excl, "n_flagged": n_flag,
            "eog_rule_flags": n_eog_flag, "interp_rule_flags": n_interp_flag,
        },
        "status": "ok",
    })
    log.info(f"[01_ingest_bids] DONE — proceed to: python3 scripts/neurophase/02_qc.py")


if __name__ == "__main__":
    main()
