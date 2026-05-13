"""Append a longitudinal admissibility row to the history JSONL.

This tool is the cumulative-measurement layer over the
γ-ledger bridge. Each invocation runs the bridge against the
current ledger, computes the headline metrics, and appends a
deterministic row to
``artifacts/eai/benchmarks/gamma_ledger_admissibility_history.jsonl``.

Determinism: the row carries ``ledger_sha256`` and
``bridge_module_sha256`` so each historical entry is reproducible
against a specific snapshot of inputs. The wall-clock timestamp
is the only non-deterministic field; it is captured to UTC
ISO-8601 second precision so identical re-runs at different
wall-clock moments produce identical-content rows up to the
``recorded_at`` field.

Regression policy (enforced by ``--check-regression``):
- If a prior row exists with the same ``ledger_sha256`` and
  ``bridge_module_sha256``, the new row's ``admissibility_rate``
  MUST equal the prior (no determinism drift).
- Otherwise, the new row's ``admissibility_rate`` MUST be
  greater than or equal to the previous most-recent row's rate
  (no regression). Exit 2 on violation.

Exit codes:
- 0   = appended (or would-append) successfully, no regression.
- 1   = error (e.g. malformed history file).
- 2   = regression detected; the new row is still appended for
        forensic audit but the process exits non-zero so CI can
        block the change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.eai.run_gamma_ledger_through_gate import run_bridge  # noqa: E402

_HISTORY_SCHEMA = "EAI-GAMMA-ADMISSIBILITY-HISTORY-v1"


def _utc_now_iso_seconds() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_row(ledger_path: Path, bridge_module_path: Path) -> dict[str, Any]:
    report = run_bridge(ledger_path, bridge_module_path)
    return {
        "schema_version": _HISTORY_SCHEMA,
        "recorded_at": _utc_now_iso_seconds(),
        "ledger_path": str(ledger_path),
        "ledger_version": report["ledger_version"],
        "ledger_sha256": report["ledger_sha256"],
        "bridge_module_sha256": report["bridge_module_sha256"],
        "total_entries": report["total_entries"],
        "gate_verdict_counts": report["gate_verdict_counts"],
        "hash_bound_count": report["hash_bound_count"],
        "candidate_total": report["candidate_total"],
        "admissible_evidence": report["admissible_evidence"],
        "admissibility_rate": report["admissibility_rate"],
    }


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _check_regression(history: list[dict[str, Any]], new_row: dict[str, Any]) -> tuple[bool, str]:
    """Return ``(is_regression, reason)``.

    Two independent guards, BOTH must pass:

    1. **Determinism**: if the same ``ledger_sha256`` +
       ``bridge_module_sha256`` appears in history, the new
       row's rate MUST equal it (gate must be deterministic).
    2. **Monotone non-decrease vs most-recent**: regardless of
       input-hash match, the new rate MUST be greater than or
       equal to ``history[-1].admissibility_rate``. This blocks
       a rollback to older inputs that had a lower historical
       rate — same-input match is not a free pass to undo a
       legitimate later improvement.
    """

    if not history:
        return False, "first_row"

    # Guard 1: determinism on identical inputs
    same_inputs = [
        r
        for r in history
        if r.get("ledger_sha256") == new_row["ledger_sha256"]
        and r.get("bridge_module_sha256") == new_row["bridge_module_sha256"]
    ]
    if same_inputs:
        prior_same = same_inputs[-1]
        if prior_same["admissibility_rate"] != new_row["admissibility_rate"]:
            return True, (
                f"determinism drift: same inputs but "
                f"prior={prior_same['admissibility_rate']} vs "
                f"new={new_row['admissibility_rate']}"
            )

    # Guard 2: monotone non-decrease vs most-recent committed row
    prior_recent = history[-1]
    if new_row["admissibility_rate"] < prior_recent["admissibility_rate"]:
        return True, (
            f"admissibility regression vs most-recent: "
            f"prior={prior_recent['admissibility_rate']} "
            f"vs new={new_row['admissibility_rate']}"
        )

    if same_inputs:
        return False, "deterministic_match_prior"
    return False, "non_decreasing_rate"


def append_row(
    history_path: Path, row: dict[str, Any], *, check_regression: bool
) -> tuple[bool, str]:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = _load_history(history_path)
    is_regression, reason = _check_regression(history, row)

    # Always write, even on regression — the row is forensic
    # evidence. CI uses the non-zero exit to block the change.
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")

    return is_regression, reason


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Append a longitudinal admissibility row to the history JSONL; "
            "optionally fail on regression."
        ),
    )
    parser.add_argument("--ledger", default="evidence/gamma_ledger.json")
    parser.add_argument(
        "--history",
        default="artifacts/eai/benchmarks/gamma_ledger_admissibility_history.jsonl",
    )
    parser.add_argument(
        "--check-regression",
        action="store_true",
        help="Exit non-zero if the new row regresses the admissibility rate.",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    bridge_module_path = _REPO_ROOT / "core" / "eai" / "gamma_bridge.py"
    row = _build_row(ledger_path, bridge_module_path)

    history_path = Path(args.history)
    is_regression, reason = append_row(history_path, row, check_regression=args.check_regression)

    print(
        json.dumps(
            {
                "appended_to": str(history_path),
                "recorded_at": row["recorded_at"],
                "admissibility_rate": row["admissibility_rate"],
                "regression": is_regression,
                "reason": reason,
            },
            sort_keys=True,
        )
    )
    if args.check_regression and is_regression:
        return 2
    return 0


# Convenience for unit tests
def compute_history_digest(history: list[dict[str, Any]]) -> str:
    """Return a stable digest of the audit-relevant fields across the
    full history (excludes ``recorded_at`` which is wall-clock)."""
    payload: list[dict[str, Any]] = []
    for r in history:
        copy_r = {k: v for k, v in r.items() if k != "recorded_at"}
        payload.append(copy_r)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
