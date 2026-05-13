# EAI False-Promotion Benchmark v1

## Purpose

Measure the **gate's** behaviour on a labelled population of claims.
This benchmark is a computational verification harness for the EAI
research track. It does **not** prove that EAI eliminates false
promotion in the wild; it pins behaviour on a deterministic, audited
synthetic dataset so regressions in the gate are caught in CI.

## Dataset composition

`data/eai_calibration/false_promotion_benchmark_v1.jsonl` — 120 rows.

| slice | rows | `expected_status` | notes |
|---|---|---|---|
| `FP-EVD-STAT-*` | 10 | EVIDENCE | bounded statistical claims |
| `FP-EVD-SW-*` | 10 | EVIDENCE | software unit-test bounded claims |
| `FP-EVD-FACT-*` | 10 | EVIDENCE | bounded factual reference claims |
| `FP-EVD-METH-*` | 10 | EVIDENCE | methodological bounded claims |
| `FP-KILL-PHYS-*` | 10 | KILLED | physical impossibility (caught by `violates_physical_plausibility`) |
| `FP-KILL-CONTRA-*` | 30 | KILLED | contradiction-marker hit |
| `FP-QUAR-*` | 20 | QUARANTINED | ambiguous claims; revalidation withheld |
| `FP-TRAP-*` | 20 | KILLED | adversarial overclaim traps (`trap_type` ∈ 6 categories) |

`trap_type` covers: `authority_inflation`, `boundary_expansion`,
`fake_citation`, `universal_claim`, `software_claim_without_execution`,
`causal_overclaim`.

## Row schema

```jsonc
{
  "claim_id": "FP-EVD-STAT-001",
  "claim_text": "...",
  "expected_status": "EVIDENCE|KILLED|QUARANTINED",
  "claim_type": "factual|causal|predictive|software|methodological|...",
  "required_boundary": ["..."],
  "required_falsifiers": ["..."],
  "expected_failure_reason": "none|contradiction_marker_hit|physical_plausibility_violation|awaiting_revalidation",
  "trap_type": "none|authority_inflation|boundary_expansion|fake_citation|universal_claim|software_claim_without_execution|causal_overclaim"
}
```

## Metric definitions

- **true_positive_evidence**: rows where `expected_status == "EVIDENCE"` AND `actual_status == "EVIDENCE"`.
- **false_promotion_count**: rows where `expected_status != "EVIDENCE"` AND `actual_status == "EVIDENCE"`.
- **false_kill_count**: rows where `expected_status == "EVIDENCE"` AND `actual_status == "KILLED"`.
- **quarantine_accuracy**: fraction of `expected="QUARANTINED"` rows that the gate actually QUARANTINED.
- **boundary_violation_count**: alias for `false_promotion_count` framed as "evidence promoted outside its declared boundary." Hard floor is 0.
- **trap_detection_rate**: of all `trap_type != "none"` rows, the fraction that ended up KILLED or QUARANTINED (never promoted).
- **false_promotion_rate**: `false_promotion_count / count(expected_status != "EVIDENCE")`.

## Thresholds (PASS/FAIL)

```json
{
  "max_false_promotion_rate": 0.02,
  "max_boundary_violation_count": 0
}
```

`decision` is `PASS` iff both thresholds are satisfied; otherwise `FAIL`.
The runner exits 0 on PASS, 2 on FAIL.

## Determinism

- No network, no LLM calls, no PRNG.
- The artifact ledger is constructed with `clock=_frozen_clock` so
  timestamps are fixed at `1970-01-01T00:00:00+00:00`.
- The report's `dataset_sha256` is the SHA-256 of the dataset file
  bytes — any drift in the dataset invalidates the report identity.
- `tests/eai/calibration/test_false_promotion_benchmark.py::test_report_is_deterministic_across_two_runs`
  asserts two consecutive runs produce byte-identical results on the
  audit-relevant fields.

## Known limitations

- **Synthetic population**: rows are hand-curated bounded claims and
  six families of overclaim. The benchmark cannot, by itself, infer
  performance on field-collected claims.
- **Boundary inputs are derived from the row** (`required_boundary` →
  `BoundaryCard.valid_for`); the dataset cannot test the case where a
  caller upstream of the gate fabricates a wider boundary than the
  evidence supports. Such adversarial-caller robustness lives in
  `tests/eai/redteam/`.
- **Quarantine basin** is reached by the runner withholding
  `revalidation_passed=False`, mirroring the contract that the gate
  withholds (not rejects) on incomplete revalidation. A real
  deployment may reach this basin via different mechanisms (e.g.
  retention_hash invalid) — those branches are exercised in
  `tests/eai/integration/test_engine_iev_gate_kill_and_safe_hash.py`.
- **`false_promotion_rate` is bounded below the threshold by
  construction of the dataset**: the gate's published contract
  guarantees zero false promotions on the listed failure modes. The
  benchmark's value is *regression detection* — any future change to
  the gate that breaks one of these failure modes will surface as a
  metric drift.

## Exact commands

```bash
# Run the benchmark, write the report
PYTHONPATH=. python tools/eai/run_false_promotion_benchmark.py \
  --dataset data/eai_calibration/false_promotion_benchmark_v1.jsonl \
  --out artifacts/eai/benchmarks/false_promotion_report_v1.json

# Tests
PYTHONPATH=. python -m pytest tests/eai/calibration/test_false_promotion_benchmark.py -q
PYTHONPATH=. python -m pytest tests/eai/protocol/test_artifact_ledger_deterministic_clock.py -q
PYTHONPATH=. python -m pytest tests/eai/ -q
```

## Report path

`artifacts/eai/benchmarks/false_promotion_report_v1.json`

Checked into the repo as the latest deterministic transcript. The CI
slice may overwrite it on regeneration; the report's `dataset_sha256`
is the audit-stable identity.

## Claim boundary

> EAI false-promotion benchmark v1 measures gate behavior on a
> synthetic calibrated dataset.

The benchmark **does not** establish:

- that EAI proves intelligence,
- that EAI eliminates false promotion in production,
- that EAI is a model of cognition or the brain,
- that the gate is scientifically validated on field data,
- any claim about AGI, consciousness, or neuroscience equivalence.

These statements are explicitly out of scope and any phrasing that
implies them must be revised.
