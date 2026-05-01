#!/usr/bin/env python3
"""Stage 07 — Verdict synthesizer (NP-RUN1-S07-v1.0).

Reads:
  neurophase/results/existence_report.json   (from Stage 04)
  neurophase/results/utility_report.json     (from Stage 05)
  neurophase/results/robustness_report.json  (from Stage 06)

Applies the pre-registered integration-ceiling rule table
(see contracts/neurophase_run1.yaml → integration_ceiling) and the
artifact / specificity gates from NP-RUN1-VERDICT-v1.1.

Writes the `results:` section and `integration_ceiling:` assignment into
neurophase/results/RUN1_VERDICT.yaml. Does NOT set `verdict_locked: true` —
that must be done manually after review.

Refuses to overwrite a locked verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from _common import (
    REPO_ROOT,
    append_ledger,
    load_config,
    load_contract,
    load_qc_summary,
    parse_std_args,
    require_provenance_freeze,
    set_global_seed,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_yaml,
)


def _assign_ceiling(h1: str, h2: str, rob: dict) -> tuple[str, str]:
    if rob.get("artifact_flag"):
        return "INVALID", "artifact_flag=True; preprocessing + ICA re-review required"
    if rob.get("topographic_specificity_ok") is False and h1 == "CONFIRMED":
        return "UNRESOLVED", (
            f"H1 passed thresholds but topographic specificity failed "
            f"(frontocentral − occipital / SD = {rob.get('frontocentral_vs_occipital_sd_ratio')}); "
            f"H1 downgraded to INCONCLUSIVE per pre-registered rule."
        )
    if h1 == "REJECTED":
        return "EEG_TRACK_CLOSED", "Update CLAIMS.yaml: FMθ → REJECTED. No further EEG runs."
    if h1 == "INCONCLUSIVE_UNDERPOWERED":
        return "UNDERPOWERED_NULL", "Run 2 (ds004295) required for disambiguation; cannot claim rejection."
    if h1 == "CONFIRMED":
        if h2 in ("CONFIRMED", "CONFIRMED_WEAK"):
            tag = "CANDIDATE_ADAPTER"
            if h2 == "CONFIRMED_WEAK":
                return tag, (
                    "H2=CONFIRMED_WEAK (statistically significant but d < 0.20). "
                    "Proceed to Run 3 (IGT) replication with explicit effect-size caveat."
                )
            return tag, "Proceed to Run 3 (IGT) replication. No NFI integration until replicated."
        if h2 == "REJECTED":
            return "WITNESS_ONLY", "Proceed to Run 2 (ds004295) for utility replication attempt."
        if h2 == "INCONCLUSIVE":
            return "WITNESS_PENDING", "H2 inconclusive — Run 2 required before utility verdict."
    if h1 == "INCONCLUSIVE":
        return "UNRESOLVED", "Proceed to Run 2 with identical H1 protocol; no ceiling assignment."
    return "UNRESOLVED", f"Unhandled state: H1={h1} H2={h2}"


def main() -> None:
    args = parse_std_args("07_write_verdict")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("07_write_verdict", cfg)

    results_dir = REPO_ROOT / cfg["paths"]["results_dir"]
    verdict_path = results_dir / "RUN1_VERDICT.yaml"

    if not verdict_path.exists():
        sys.exit(f"[FAIL-CLOSED] verdict template missing: {verdict_path}")
    with verdict_path.open() as f:
        verdict = yaml.safe_load(f)
    if verdict.get("verdict_locked", False):
        sys.exit("[FAIL-CLOSED] RUN1_VERDICT.yaml already locked; refusing to overwrite.")

    h1_path = results_dir / "existence_report.json"
    h2_path = results_dir / "utility_report.json"
    rob_path = results_dir / "robustness_report.json"
    for p, label in [(h1_path, "H1"), (h2_path, "H2"), (rob_path, "robustness")]:
        if not p.exists():
            sys.exit(f"[FAIL-CLOSED] {label} report missing: {p}")

    h1 = json.loads(h1_path.read_text())
    h2 = json.loads(h2_path.read_text())
    rob = json.loads(rob_path.read_text())

    h1_verdict = h1.get("verdict")
    h2_verdict = h2.get("verdict")

    ceiling, rationale = _assign_ceiling(h1_verdict, h2_verdict, rob)

    # Populate verdict.results
    r = verdict.setdefault("results", {})
    r["analysis_completion_timestamp"] = utc_now_iso()
    r["n_subjects_analyzed"] = h1.get("n_subjects_ok")

    r["H1_existence"] = {
        "result": h1_verdict,
        "sign_consistency": h1.get("sign_consistency"),
        "group_t_statistic": h1.get("group_t_statistic"),
        "group_t_pvalue": h1.get("group_t_pvalue"),
        "cohens_d": h1.get("cohens_d"),
        "ci_95_bootstrap": h1.get("beta_ci95_bootstrap"),
        "ci_method": h1.get("beta_ci_method"),
        "effect_direction": h1.get("effect_direction"),
        "permutation_null_valid": h1.get("permutation_null_valid"),
        "power_constraint_active": h1.get("power_constraint_active"),
        "mde_threshold": h1.get("mde_cohens_d_threshold"),
    }

    r["H2_utility"] = {
        "result": h2_verdict,
        "mean_delta_auc": h2.get("delta_auc_NB_minus_B_primary", {}).get("mean"),
        "t_statistic": h2.get("delta_auc_NB_minus_B_primary", {}).get("t"),
        "t_pvalue": h2.get("delta_auc_NB_minus_B_primary", {}).get("t_p"),
        "cohens_d": h2.get("delta_auc_NB_minus_B_primary", {}).get("d"),
        "ci_95_bootstrap": h2.get("delta_auc_NB_minus_B_primary", {}).get("ci95"),
        "ci_method": h2.get("delta_auc_NB_minus_B_primary", {}).get("ci_method"),
    }

    r["robustness"] = {
        "effect_specific_to_theta_frontocentral": rob.get("topographic_specificity_ok"),
        "artifact_flag": rob.get("artifact_flag"),
        "fraction_channels_positive_theta": rob.get("fraction_positive_theta"),
        "fraction_channels_positive_alpha": rob.get("fraction_positive_alpha"),
        "fraction_channels_positive_beta": rob.get("fraction_positive_beta"),
        "frontocentral_vs_occipital_sd_ratio": rob.get("frontocentral_vs_occipital_sd_ratio"),
    }

    r["integration_ceiling"] = {
        "current_status": ceiling,
        "rationale": rationale,
    }

    next_action = {
        "EEG_TRACK_CLOSED": "Update CLAIMS.yaml; neurophase EEG track closed.",
        "WITNESS_ONLY": "Proceed to Run 2 (ds004295).",
        "WITNESS_PENDING": "Proceed to Run 2 (ds004295) for H2 resolution.",
        "CANDIDATE_ADAPTER": "Proceed to Run 3 (IGT) independent replication.",
        "UNRESOLVED": "Proceed to Run 2 with identical H1 protocol.",
        "UNDERPOWERED_NULL": "Run 2 required for disambiguation; cannot claim rejection.",
        "INVALID": "HALT — artifact detected; preprocessing/ICA re-review required before any verdict.",
    }.get(ceiling, "See rationale.")
    r["next_action"] = next_action

    r["input_artifact_hashes"] = {
        "existence_report": {"path": str(h1_path), "sha256": sha256_file(h1_path)},
        "utility_report": {"path": str(h2_path), "sha256": sha256_file(h2_path)},
        "robustness_report": {"path": str(rob_path), "sha256": sha256_file(rob_path)},
    }

    write_yaml(verdict_path, verdict)
    append_ledger(cfg, {"stage": "07_write_verdict",
                        "output": {"verdict_path": str(verdict_path),
                                   "verdict_sha256": sha256_file(verdict_path),
                                   "ceiling": ceiling,
                                   "h1": h1_verdict, "h2": h2_verdict,
                                   "artifact_flag": rob.get("artifact_flag")},
                        "status": "ok"})
    log.info("=" * 72)
    log.info(f"FINAL VERDICT")
    log.info(f"  H1 = {h1_verdict}")
    log.info(f"  H2 = {h2_verdict}")
    log.info(f"  Integration ceiling = {ceiling}")
    log.info(f"  Rationale: {rationale}")
    log.info(f"  Next action: {next_action}")
    log.info("=" * 72)
    log.info(f"Wrote: {verdict_path}  (verdict_locked still FALSE — set manually after review)")


if __name__ == "__main__":
    main()
