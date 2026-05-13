# EAI ↔ γ-Ledger Bridge v1

## Purpose

Run every entry in `evidence/gamma_ledger.json` through the EAI
gate and emit a deterministic decision report. This is a
**measurement of admissibility** of the γ-ledger entries under the
EAI discipline — *not* a re-assertion of the entries' published
status and *not* a validation of the γ scaling law.

The bridge answers exactly one operational question:

> *Of the N γ-ledger entries currently tagged
> EVIDENCE_CANDIDATE, how many would pass the EAI gate as EVIDENCE
> today, and for the ones that do not, what is the blocking
> failure mode?*

## Mapping (pure, deterministic)

| Ledger field | EAI input |
|---|---|
| `description` | `ClaimCard.claim_text` (with `[gate-tags: …]` header if failure flags present) |
| `substrate` | `BoundaryCard.valid_for[0]` and `tested_conditions[0]` |
| `derivation_method` | `ReproducibilityManifest.commands` (auxiliary trace, not a boundary axis) |
| `data_sha256` (valid hex) | `ReproducibilityManifest.artifact_hash`, `hash_bound=True` |
| `data_sha256` missing | computed metadata-only fallback hash, `hash_bound=False` |
| `status == EVIDENCE_CANDIDATE_NULL_FAILED` | `status_tag=null_screen_rejected` ⇒ contradiction marker |
| `status == LOCAL_STRUCTURAL_EVIDENCE_ONLY` or `tier == LOCAL_STRUCTURAL` | `status_tag=local_structural_only` |
| `tier == NUMERICAL_INTERNAL` | `status_tag=numerical_internal_only` |
| `rerun_command` | `ReproducibilityManifest.commands[0]` |

**Routing policy:**

* Any failure-state tag → `KILLED` via falsification gate.
* Clean entry, no real hash binding → `QUARANTINED` (revalidation withheld).
* Clean entry + real hash binding → `EVIDENCE`.

The bridge is **read-only**: it never mutates the γ ledger. Verification of read-only behaviour is pinned by `tests/eai/integration/test_gamma_bridge.py::test_bridge_does_not_mutate_input_entry`.

## Determinism contract

* No network, no LLM, no PRNG.
* Frozen UTC clock `1970-01-01T00:00:00+00:00` injected into the artifact ledger.
* Two consecutive runs produce byte-identical JSON.
* `ledger_sha256` and `bridge_module_sha256` are SHA-256 of the
  exact files used, providing audit-stable identity.

## Report schema (`EAI-GAMMA-BRIDGE-v1`)

```jsonc
{
  "schema_version": "EAI-GAMMA-BRIDGE-v1",
  "ledger_path": "evidence/gamma_ledger.json",
  "ledger_version": "2.0.0",
  "ledger_sha256": "...",
  "bridge_module_sha256": "...",
  "frozen_clock": "1970-01-01T00:00:00+00:00",
  "total_entries": 10,
  "gate_verdict_counts": {"EVIDENCE": 2, "KILLED": 4, "QUARANTINED": 4},
  "hash_bound_count": 3,
  "candidate_total": 7,
  "admissible_evidence": 2,
  "admissibility_rate": 0.285714,
  "per_entry": [ … ]
}
```

## Latest measurement (committed transcript)

`artifacts/eai/benchmarks/gamma_ledger_gate_decisions_v1.json`

| metric | value |
|---|---|
| total_entries | 10 |
| EVIDENCE | 2 |
| KILLED | 4 |
| QUARANTINED | 4 |
| hash_bound_count | 3 |
| candidate_total (`EVIDENCE_CANDIDATE`) | 7 |
| admissible_evidence | 2 |
| **admissibility_rate** | **0.2857** |

The two entries that currently pass the gate as EVIDENCE are
`eeg_physionet` and `eeg_resting`. The remaining five
EVIDENCE_CANDIDATE entries are QUARANTINED pending hash binding
(`data_sha256` is `null` in the ledger).

## Known limitations

- **Methodology-only routing**: the bridge routes via the gate's
  existing levers (falsification gate, `can_be_promoted`, revalidation).
  It does not invent new gate semantics for γ entries — that would
  conflate the discipline with the substrate.
- **Synthetic fallback hash**: missing `data_sha256` produces a
  deterministic metadata-only digest. This is *intentionally not*
  bound to real data; the QUARANTINE basin is reached by withholding
  revalidation, not by pretending the hash is real.
- **No empirical claim**: the report does not assert that γ ≈ 1.0
  is true, false, validated, falsified, or scientifically resolved.
  It records *whether the current ledger entry would pass the gate*.

## Exact commands

```bash
PYTHONPATH=. python tools/eai/run_gamma_ledger_through_gate.py \
  --ledger evidence/gamma_ledger.json \
  --out artifacts/eai/benchmarks/gamma_ledger_gate_decisions_v1.json

PYTHONPATH=. python -m pytest tests/eai/integration/test_gamma_bridge.py -q
```

## Claim boundary

> The EAI ↔ γ-ledger bridge v1 measures admissibility of γ-ledger
> entries under the EAI gate, on a frozen-clock deterministic run.

**Forbidden phrasings** (replicated from
`docs/research/EAI_FALSE_PROMOTION_BENCHMARK_V1.md`):

- "EAI validates γ ≈ 1.0"
- "EAI rejects γ ≈ 1.0"
- "Bridge proves the γ scaling law"
- "Bridge demonstrates intelligence"
- "Substrate X is scientifically validated"
- "Substrate X is scientifically refuted"

The bridge produces a *gate verdict on the current ledger state*.
Updates to either side (ledger or gate) can change the verdict;
the verdict is not a property of the substrate.
