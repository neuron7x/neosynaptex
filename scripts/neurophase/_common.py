"""Shared helpers for the neurophase Run 1 pipeline.

Provides:
  - config / contract loading with SHA-256 provenance stamps
  - structured logging to `neurophase/logs/<stage>.log` + stdout
  - a deterministic rule-table audit engine (no heuristic branching)
  - chmod-based freeze helpers (manifest + feature store)
  - LEDGER append (immutable, hash-stamped)
  - fail-closed gate helpers (PROVENANCE_FREEZE, analyst_lock, feature freeze)

All pipeline stages import from here. Design invariants:
  1. No silent branching. Every decision produces a structured record.
  2. Fail-closed by default. Missing prerequisites halt with actionable messages.
  3. SHA-256 hashes bind every artifact to the run_id in LEDGER.yaml.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "neurophase_run1.yaml"

SEV_HALT = "HALT"
SEV_ERROR = "ERROR"
SEV_WARN = "WARN"
SEV_FLAG = "FLAG"
SEV_INFO = "INFO"
_SEV_LOG = {
    SEV_HALT: logging.CRITICAL,
    SEV_ERROR: logging.ERROR,
    SEV_WARN: logging.WARNING,
    SEV_FLAG: logging.INFO,
    SEV_INFO: logging.INFO,
}


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.exists():
        sys.exit(f"[FAIL-CLOSED] config not found: {p}")
    with p.open() as f:
        cfg = yaml.safe_load(f)
    cfg["_config_path"] = str(p)
    cfg["_config_sha256"] = sha256_file(p)
    return cfg


def load_contract(cfg: dict[str, Any]) -> dict[str, Any]:
    cpath = REPO_ROOT / cfg["contract"]
    if not cpath.exists():
        sys.exit(f"[FAIL-CLOSED] contract not found: {cpath}")
    with cpath.open() as f:
        contract = yaml.safe_load(f)
    contract["_contract_path"] = str(cpath)
    contract["_contract_sha256"] = sha256_file(cpath)
    return contract


def set_global_seed(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)


def sha256_file(path: Path | str, chunk: int = 1 << 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def setup_logging(stage: str, cfg: dict[str, Any]) -> logging.Logger:
    logs_dir = REPO_ROOT / cfg["paths"].get("out_root", "neurophase") / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{stage}.log"
    logger = logging.getLogger(f"neurophase.{stage}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.propagate = False
    return logger


def append_ledger(cfg: dict[str, Any], entry: dict[str, Any]) -> None:
    ledger_path = REPO_ROOT / cfg["paths"]["ledger"]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if ledger_path.exists() and ledger_path.stat().st_size > 0:
        with ledger_path.open() as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, list):
                existing = loaded
            elif isinstance(loaded, dict) and "entries" in loaded:
                existing = loaded["entries"]
    entry.setdefault("timestamp", utc_now_iso())
    entry.setdefault("run_id", cfg.get("run_id"))
    existing.append(entry)
    tmp = ledger_path.with_suffix(".tmp")
    with tmp.open("w") as f:
        yaml.safe_dump(existing, f, sort_keys=False)
    tmp.replace(ledger_path)


def write_ledger_halt(cfg: dict[str, Any], stage: str, reason: str, detail: dict[str, Any]) -> None:
    append_ledger(cfg, {"stage": stage, "status": "HALT", "reason": reason, "detail": detail})


def apply_rule(rule: dict[str, Any], values: dict[str, Any]) -> bool:
    """Deterministic rule evaluation. Operators: eq / gt / lt / ge / le / ne."""
    v = values.get(rule["detail_key"], 0)
    op, thr = rule["operator"], rule["threshold"]
    if op == "eq": return v == thr
    if op == "ne": return v != thr
    if op == "gt": return v > thr
    if op == "lt": return v < thr
    if op == "ge": return v >= thr
    if op == "le": return v <= thr
    raise ValueError(f"unknown operator: {op}")


def evaluate_rules(rules: list[dict[str, Any]], values: dict[str, Any],
                   logger: logging.Logger | None = None,
                   subject_id: str | None = None) -> list[dict[str, Any]]:
    """Apply a rule table, return list of fired rule records.
    Emits structured log entries with rule_id + severity. No silent branching.
    """
    fired: list[dict[str, Any]] = []
    for rule in rules:
        if apply_rule(rule, values):
            rec = {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "severity": rule["severity"],
                "value": values.get(rule["detail_key"]),
            }
            fired.append(rec)
            if logger is not None:
                sev = rule["severity"]
                prefix = f"{subject_id} " if subject_id else ""
                logger.log(_SEV_LOG.get(sev, logging.INFO),
                           f"{prefix}AUDIT [{rule['rule_id']}] {sev}: {rule['description']} | value={rec['value']}")
    return fired


def freeze_file(path: Path) -> str:
    """Set file read-only (owner+group+other read). Returns SHA-256 of the frozen file."""
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return sha256_file(path)


def is_frozen(path: Path) -> bool:
    mode = path.stat().st_mode
    return not bool(mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def freeze_dir_tree(root: Path) -> dict[str, str]:
    """chmod -R a-w on all files in tree. Returns {relative_path: sha256}."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            out[str(p.relative_to(root))] = sha256_file(p)
    return out


def require_provenance_freeze(cfg: dict[str, Any]) -> dict[str, Any]:
    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    freeze_path = qc_dir / "PROVENANCE_FREEZE.yaml"
    if not freeze_path.exists():
        sys.exit(f"[FAIL-CLOSED] PROVENANCE_FREEZE.yaml missing; run stage 01 first: {freeze_path}")
    with freeze_path.open() as f:
        pf = yaml.safe_load(f)
    if not pf.get("provenance_lock", False):
        sys.exit("[FAIL-CLOSED] provenance_lock is not true in PROVENANCE_FREEZE.yaml")
    current = load_contract(cfg)["_contract_sha256"]
    if pf.get("contract_sha256") != current:
        sys.exit(f"[FAIL-CLOSED] contract hash drift since provenance freeze "
                 f"(frozen={pf.get('contract_sha256')[:12]}… vs current={current[:12]}…). Halt and investigate.")
    return pf


def load_qc_summary(cfg: dict[str, Any]) -> dict[str, Any]:
    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    summary_path = qc_dir / "QC_SUMMARY.yaml"
    if not summary_path.exists():
        sys.exit(f"[FAIL-CLOSED] QC_SUMMARY.yaml missing: {summary_path}")
    with summary_path.open() as f:
        s = yaml.safe_load(f)
    if not s.get("analyst_lock", False):
        sys.exit("[FAIL-CLOSED] analyst_lock is not true. Review QC and set it manually.")
    return s


def assert_features_frozen(features_dir: Path) -> None:
    for p in features_dir.glob("*_features.h5"):
        if not is_frozen(p):
            sys.exit(f"[FAIL-CLOSED] feature store not frozen; {p} still writable. "
                     f"Run: chmod -R a-w {features_dir}")


def parse_std_args(stage: str) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog=f"neurophase.{stage}")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--bids_root", default=None, help="override cfg.paths.bids_root")
    ap.add_argument("--dry_run", action="store_true", help="validate without writing")
    return ap.parse_args()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(obj, f, indent=2, default=str)


def write_yaml(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump(obj, f, sort_keys=False)


def enforce_pipeline_halt_fraction(n_excluded: int, n_total: int, limit: float,
                                    cfg: dict[str, Any], stage: str,
                                    logger: logging.Logger) -> None:
    if n_total <= 0:
        return
    frac = n_excluded / n_total
    if frac > limit:
        logger.critical(f"[HALT] {stage}: exclusion fraction {frac:.3f} > {limit:.3f}")
        write_ledger_halt(cfg, stage, "exclusion_fraction_exceeded",
                          {"n_excluded": n_excluded, "n_total": n_total, "fraction": frac, "limit": limit})
        sys.exit(2)
