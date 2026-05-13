# EAI Mandatory Artifact Stack (May 2026 Baseline)

## Purpose
This document defines the required artifact inventory for the EAI research track against a May 2026 baseline (EU AI Act / NIST AI RMF 2.0 / ISO-IEC 42001-oriented governance).

## Status Legend
- `IMPLEMENTED`: artifact exists with owner + update path.
- `PARTIAL`: artifact exists but lacks one or more required sections.
- `MISSING`: artifact not present yet.
- `OUT_OF_SCOPE`: not currently claimed by this repository profile.

## 1) Regulatory / Compliance-as-Code

| Artifact | Status | Location / Plan | Exit Criteria |
|---|---|---|---|
| Conformity Assessment Report (CAR) | MISSING | `docs/compliance/CAR.md` (planned) | CE-conformity mapping + controls matrix + residual risk log |
| Fundamental Rights Impact Assessment (FRIA) | MISSING | `docs/compliance/FRIA.md` (planned) | Stakeholder analysis + rights risk scenarios + mitigations |
| Annex IV Technical Documentation | PARTIAL | `docs/architecture/eai-engine-operational-model.md`, `docs/eai/EAI_SPEC_V1_HIGH_ASSURANCE.md` | Add Annex IV section map, traceable IDs, model lifecycle evidence |
| Post-Market Surveillance Plan (PMSP) | MISSING | `docs/compliance/PMSP.md` (planned) | Drift triggers, incident response SLA, reporting cadence |
| AI System Life-Cycle Description (ISO/IEC 5338) | MISSING | `docs/compliance/AI_LIFECYCLE_5338.md` (planned) | Stage-gate lifecycle from data intake to decommission |

## 2) Architecture Verification & Safety

| Artifact | Status | Location / Plan | Exit Criteria |
|---|---|---|---|
| SBOM for AI | PARTIAL | Runtime deps in `pyproject.toml`; add model/data/dependency SBOM at `artifacts/sbom/eai_sbom.json` | Includes code deps + model/data assets + hashes |
| Adversarial Resilience Audit | PARTIAL | `tests/eai/redteam/` + `docs/research/EAI_ENGINE_PR1_IMPLEMENTATION_REPORT.md` | Add formal attack matrix + coverage report + unresolved findings |
| Drift Analysis & Calibration Report | PARTIAL | `core/eai/calibration.py`, `tools/eai/run_calibration.py`, `data/eai_calibration/` | Add periodic drift report template + threshold governance |
| Formal Verification Proofs | MISSING | `docs/verification/formal_proofs.md` (planned) | Invariant proofs or machine-checkable proof obligations |
| Computational Budget & Carbon Disclosure | MISSING | `docs/compliance/compute_carbon_disclosure.md` (planned) | Compute ledger + kgCO2 methodology + run metadata |

## 3) Epistemic / Research Artifacts

| Artifact | Status | Location / Plan | Exit Criteria |
|---|---|---|---|
| Reproducibility Manifest | PARTIAL | Add `artifacts/repro/repro_manifest.json` with SHA-256, seeds, environment lock | Re-run gives reproducible outputs for reference suite |
| Semantic Interoperability Schema | PARTIAL | `core/eai/constraint_index.py`, `schemas/*.schema.json` | Add ontology/predicate catalog + substrate mapping table |
| Agnostic Performance Benchmarking | MISSING | `docs/research/benchmarking_agnostic_2026.md` (planned) | Closed-set benchmark results + protocol + confidence bounds |
| Bias & Fairness Audit Trail | MISSING | `docs/governance/bias_fairness_audit_trail.md` (planned) | Protected-group metrics + mitigation decisions + change log |

## 4) Agent / Multi-Agent Logic

| Artifact | Status | Location / Plan | Exit Criteria |
|---|---|---|---|
| Agent Safety & Termination Protocol | PARTIAL | `docs/protocols/iev-gate-v1.md` + kill-path tests | Add emergency-stop runbook + privilege boundaries |
| Inter-Agent Communication Logs (IACL) | MISSING | `artifacts/agent_logs/iacl/` (planned) | Structured message log schema + retention policy |
| State Transition Transparency Map | PARTIAL | lifecycle in `core/eai/intelligence_cycle.py` + docs | Add single-page state transition diagram |
| Human-Oversight Instruction Manual | MISSING | `docs/governance/human_oversight_manual.md` (planned) | Operator intervention playbook at critical checkpoints |

## 5) Data Governance

| Artifact | Status | Location / Plan | Exit Criteria |
|---|---|---|---|
| Data Lineage Map | MISSING | `docs/data/data_lineage_map.md` (planned) | Source-to-tensor lineage with transforms |
| Informed Consent Metadata | MISSING | `docs/data/informed_consent_metadata.md` (planned) | Consent/legal basis registry + auditability |
| Data Quality Assessment (DQA) | MISSING | `docs/data/dqa_report.md` (planned) | Completeness, representativeness, error profile, controls |

## Prioritized Remediation Order
1. Regulatory baselines (CAR, FRIA, Annex IV map, PMSP, lifecycle doc).
2. Safety baselines (AI SBOM, formal drift report, safety termination runbook).
3. Reproducibility + data governance (manifest, lineage, DQA, consent metadata).
4. Multi-agent transparency + fairness trail.

## Non-Claim Boundary (Fail-Closed)
Until the `MISSING` items above are implemented, this repository **must not** claim production-grade regulatory readiness, high-risk CE conformity, or complete multi-agent governance compliance.
