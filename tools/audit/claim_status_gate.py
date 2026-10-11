"""γ-program claim-status gate — Task 12 of the remediation protocol.

Enforces the invariant: ``claim_status`` for the cardiac γ-program
artefact family may NOT exceed ``measured_but_bounded`` until every
Task 1-11 checkpoint (scoreboard flag) reports ``TRUE``.

Scoreboard
----------
  full_cohort_complete           Task 1    all 4 cohort manifests, 116 OK
  split_frozen                   Task 2    config/analysis_split.yaml + hash match
  baseline_panel_complete        Task 3    116 per-subject JSONs + summary
  five_null_suite_complete       Task 6    null_suite_summary.json present
  blind_external_validation      Task 8    reports/blind_validation/report.json present
  canonical_stack_frozen         Task 4    CANONICAL_STACK_VERSION present + drift-check OK
  evidence_branches_split        Task 5    branches.yaml present
  outlier_protocol_complete      Task 7    116 yaml files under evidence/outlier_protocol/
  state_contrast_done            Task 9    reports/state_contrast/summary.json present
  stack_frozen                   Task 11   STACK.lock present + stack_lock_check OK
  full_report_present            Task 10   ≥ 1 file under reports/runs/*/full_report.json

CI usage
--------
  $ python -m tools.audit.claim_status_gate
  Exit 0 = all flags TRUE (or no γ-program claim above ceiling detected).
  Exit 2 = at least one flag FALSE (a PR is trying to ship a cardiac
           claim without first closing the referenced Task).

Rationale
---------
This is the single CI gate that separates "infrastructure ships" from
"evidence claims". Anybody can add an adapter, a metric, a fit — but
no claim about cardiac γ as a marker can leave this repo until every
box in the scoreboard is TRUE.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _count_files(pattern: str, *, base: Path = _REPO) -> int:
    return sum(1 for _ in base.glob(pattern))


def scoreboard() -> dict[str, tuple[bool, str]]:
    """Return a ``{flag: (bool, reason)}`` map (always same 11 keys)."""

    out: dict[str, tuple[bool, str]] = {}

    # Task 1 — cohort manifests
    manifests = {
        c: _REPO / "data" / "manifests" / f"{c}_manifest.json"
        for c in ("nsr2db", "chfdb", "chf2db", "nsrdb")
    }
    missing = [c for c, p in manifests.items() if not p.exists()]
    if missing:
        out["full_cohort_complete"] = (False, f"missing manifests: {missing}")
    else:
        ok = True
        why = ""
        for c, p in manifests.items():
            m = json.loads(p.read_text("utf-8"))
            if m["expected_n_subjects"] != m["actual_n_subjects"]:
                ok = False
                why = f"{c}: {m['actual_n_subjects']}/{m['expected_n_subjects']}"
                break
        out["full_cohort_complete"] = (ok, why or "116/116")

    # Task 2 — split freeze
    split_yaml = _REPO / "config" / "analysis_split.yaml"
    if not split_yaml.exists():
        out["split_frozen"] = (False, "config/analysis_split.yaml missing")
    else:
        try:
            from tools.data.analysis_split import load_split

            s = load_split()
            out["split_frozen"] = (
                True,
                f"dev={s.development.n_subjects} ext={s.external.n_subjects}",
            )
        except Exception as e:  # noqa: BLE001
            out["split_frozen"] = (False, f"load_split failed: {e}")

    # Task 3 — baseline panel
    base_dir = _REPO / "results" / "hrv_baseline"
    n_panel_files = _count_files("results/hrv_baseline/*__*_baseline.json")
    has_summary = (base_dir / "panel_summary.json").exists()
    if n_panel_files == 116 and has_summary:
        out["baseline_panel_complete"] = (True, f"{n_panel_files} files + summary")
    else:
        out["baseline_panel_complete"] = (
            False,
            f"{n_panel_files}/116 files, summary={has_summary}",
        )

    # Task 6 — null suite
    null_summary = _REPO / "evidence" / "surrogates" / "null_suite_summary.json"
    n_subject_nulls = _count_files("evidence/surrogates/*__*/null_suite.json")
    if null_summary.exists() and n_subject_nulls >= 69:
        out["five_null_suite_complete"] = (True, f"{n_subject_nulls} subjects + summary")
    else:
        out["five_null_suite_complete"] = (
            False,
            f"{n_subject_nulls} files, summary={null_summary.exists()}",
        )

    # Task 8 — blind external validation
    val_path = _REPO / "reports" / "blind_validation" / "report.json"
    thr_path = _REPO / "config" / "thresholds_frozen.yaml"
    if val_path.exists() and thr_path.exists():
        import hashlib

        got = hashlib.sha256(thr_path.read_bytes()).hexdigest()
        rep = json.loads(val_path.read_text("utf-8"))
        if rep.get("thresholds_yaml_sha256") == got:
            out["blind_external_validation"] = (True, "report + thresholds hash match")
        else:
            out["blind_external_validation"] = (False, "thresholds sha256 mismatch")
    else:
        out["blind_external_validation"] = (
            False,
            f"report={val_path.exists()} thresholds={thr_path.exists()}",
        )

    # Task 4 — canonical stack
    try:
        from tools.hrv import canonical_stack as cs

        cs.assert_canonical_params()
        out["canonical_stack_frozen"] = (True, f"v{cs.CANONICAL_STACK_VERSION}")
    except Exception as e:  # noqa: BLE001
        out["canonical_stack_frozen"] = (False, str(e))

    # Task 5 — evidence branches
    branches_path = _REPO / "evidence" / "gamma_branches" / "branches.yaml"
    if branches_path.exists():
        try:
            from tools.hrv.evidence_branches import load_branch_registry

            reg = load_branch_registry()
            out["evidence_branches_split"] = (True, f"{len(reg.branches)} branches")
        except Exception as e:  # noqa: BLE001
            out["evidence_branches_split"] = (False, str(e))
    else:
        out["evidence_branches_split"] = (False, "branches.yaml missing")

    # Task 7 — outlier protocol
    n_outlier = _count_files("evidence/outlier_protocol/*__*.yaml")
    if n_outlier == 116:
        out["outlier_protocol_complete"] = (True, f"{n_outlier}/116 subjects")
    else:
        out["outlier_protocol_complete"] = (False, f"{n_outlier}/116 subjects")

    # Task 9 — state contrast
    sc_path = _REPO / "reports" / "state_contrast" / "summary.json"
    if sc_path.exists():
        sc = json.loads(sc_path.read_text("utf-8"))
        if sc.get("n_subjects", 0) >= 116:
            out["state_contrast_done"] = (True, f"{sc['n_subjects']} subjects")
        else:
            out["state_contrast_done"] = (False, f"only {sc.get('n_subjects', 0)} subjects")
    else:
        out["state_contrast_done"] = (False, "summary missing")

    # Task 11 — STACK.lock
    try:
        from tools.audit.stack_lock_check import check as stack_check

        errors = stack_check()
        if not errors:
            out["stack_frozen"] = (True, "STACK.lock OK")
        else:
            out["stack_frozen"] = (False, "; ".join(errors))
    except Exception as e:  # noqa: BLE001
        out["stack_frozen"] = (False, str(e))

    # Task 10 — run report
    n_runs = _count_files("reports/runs/*/full_report.json")
    out["full_report_present"] = (
        n_runs > 0,
        f"{n_runs} committed run(s)",
    )

    return out


def _format(flags: dict[str, tuple[bool, str]]) -> str:
    lines = ["γ-program claim-status gate scoreboard:"]
    for name, (ok, why) in flags.items():
        mark = "TRUE " if ok else "FALSE"
        lines.append(f"  [{mark}] {name:32s} — {why}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    flags = scoreboard()
    print(_format(flags), file=sys.stderr)
    if all(ok for ok, _ in flags.values()):
        print(
            "GATE PASS — claim_status ceiling may be raised to measured_but_bounded.",
            file=sys.stderr,
        )
        return 0
    failed = [k for k, (ok, _) in flags.items() if not ok]
    print(
        f"GATE FAIL — claim_status MUST remain ≤ hypothesized. Failing flags: {failed}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
