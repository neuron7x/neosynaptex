# EAI Graded Falsification + STN-Analog Falsifiability Test v1

## Pre-registration

**This document was committed BEFORE the falsifiability test was run.**
Verdict rules, dataset structure, and constants are declared here as
a pre-registration anchor. Post-hoc adjustment of any of them
requires a fresh pre-registration document with explicit operator
authorization.

## Motivation

The current EAI falsification gate is binary: `falsification_decision`
returns `(passed: bool, reason: str)`. The IEV gate's threshold is
binary too (`revalidation_passed: bool`). The user observed that the
subthalamic nucleus (STN) of the basal ganglia, via the hyperdirect
pathway, implements a **graded** gate that delays motor output
proportional to cortical conflict (Frank et al., 2006 "hold your
horses"). The EAI gate's binary form is functionally consistent with
STN but does not implement its graded firing-rate semantics.

This experiment tests whether replacing the binary scoring with
**graded conflict_strength + threshold-modulated IEV gate** reduces
false promotion on a subtle-contradiction slice that the binary gate
cannot solve.

## Hypothesis

> Graded falsification with conflict-modulated IEV threshold reduces
> false promotion on the subtle-contradiction slice of v1_1 without
> regressing true evidence on the EVIDENCE slice.

## Pre-registered verdict rules

Declared BEFORE running. Adjusting these rules post-hoc is forbidden
by CC-META-001 ROOT-3, ROOT-6, OPERATOR-5.

| Verdict | Condition |
|---|---|
| **HYPOTHESIS_SUPPORTED** | `graded.subtle_slice_false_promotion < binary.subtle_slice_false_promotion` AND `graded.true_positive_evidence >= binary.true_positive_evidence` |
| **HYPOTHESIS_FALSIFIED** | `graded.true_positive_evidence < binary.true_positive_evidence` (graded gate killed real evidence) |
| **NULL_RESULT** | neither (no measurable improvement on subtle slice; gate change had no effect) |

## Conflict-strength formula (deterministic)

```
physical_impossibility_violation   -> 1.0 (hard kill, terminating)
per full-substring marker hit      -> +0.4
per token-overlap-only hit         -> +0.15
                                       (>=2 unique tokens shared,
                                        no full substring)
clamp to [0.0, 1.0]
```

## Threshold formula (STN-analog)

```
required_revalidation_paths(c) = ceil(1 + c * 2)
  c = 0.0  -> 1 (legacy single-path)
  c = 0.5  -> 2
  c = 1.0  -> 3
```

The graded IEV gate enforces
`len(EvidenceArtifact.revalidation_evidence_paths) >= required_paths(c)`
or QUARANTINES with reason `graded_threshold_unmet`.

## Dataset v1_1 composition

150 rows total = v1 (120 rows) + 30 new:

| Slice | N | expected_status | mechanism |
|---|---|---|---|
| v1 EVIDENCE | 40 | EVIDENCE | bounded statistical/software/factual/methodological |
| v1 KILLED (physical) | 10 | KILLED | physical impossibility |
| v1 KILLED (contradiction) | 30 | KILLED | full-substring contradiction marker |
| v1 QUARANTINED | 20 | QUARANTINED | ambiguous, revalidation withheld |
| v1 adversarial traps | 20 | KILLED | overclaim families (6 trap_type) |
| **v1_1 subtle KILL** | **20** | **KILLED** | **token-overlap-only contradiction (≥2 unique tokens, no substring)** |
| **v1_1 negative-control EVIDENCE** | **10** | **EVIDENCE** | **incidentally mentions trap tokens but in clearly bounded context** |

## Latest measurement (committed)

Per `artifacts/eai/benchmarks/falsifiability_test_v1_report.json`:

```
binary.subtle_slice_false_promotion   = 19/20
graded.subtle_slice_false_promotion   = 19/20
binary.true_positive_evidence         = 50
graded.true_positive_evidence         = 50
binary.negative_control_pass_rate     = 1.0
graded.negative_control_pass_rate     = 1.0
verdict                               = NULL_RESULT
```

### Honest interpretation

The graded gate at constants `+0.15 per token-overlap hit` with
threshold `ceil(1 + c*2)` and `available_paths=2` does NOT reduce
subtle-slice false promotion measurably. The reason: each subtle row
carries 1–2 falsifier markers, so the maximum
`conflict_strength = 0.15 * 2 = 0.30` produces
`required_paths = ceil(1 + 0.30*2) = 2 = available` — gate still
promotes.

The TP slice and negative-control slice are unaffected (50/50, 10/10
in both modes). The hypothesis is **not refuted** — it is **untested
at this fidelity**. The architecture is sound; the constants are not
calibrated.

## What this artifact ships (despite NULL_RESULT)

Per CC-META-001 ROOT-3 ("failure preserved as artifact is superior
to failure hidden as silence"):

1. `core/falsification_engine.py` gains `FalsificationResult` +
   `falsification_decision_graded` (legacy `falsification_decision`
   unchanged for backwards compat).
2. `core/eai/intelligence_cycle.py` gains optional
   `EvidenceArtifact.revalidation_evidence_paths: list[str] = []`
   (default empty, no existing-caller behaviour change).
3. `core/eai/graded_gate.py` — new module
   `decide_with_graded_threshold(...)`.
4. `data/eai_calibration/false_promotion_benchmark_v1_1.jsonl` —
   the 150-row dataset, sha-pinned.
5. `tools/eai/run_falsifiability_test.py` — the deterministic runner.
6. `artifacts/eai/benchmarks/falsifiability_test_v1_report.json` —
   the NULL_RESULT transcript, byte-identical across runs.
7. `.github/workflows/eai-graded-falsifiability.yml` — CI gate
   that FAILS only on HYPOTHESIS_FALSIFIED; warns on NULL_RESULT;
   asserts byte-identical replay.

## What this artifact does NOT promote

- The graded falsification primitive is NOT promoted to default
  engine behaviour. The production engine
  (`core/eai/engine.py`) continues to use the binary
  `falsification_decision`.
- The STN-analog hypothesis is NOT claimed as supported, validated,
  confirmed, or proved.
- No constants are presented as final; the next iteration is free to
  pre-register new constants with operator authorization.

## Forbidden phrasings (binding)

The following phrasings must not appear in any file modified by this
PR or any commit message referencing this artifact:

- "graded falsification proves STN architecture"
- "EAI replicates basal ganglia"
- "STN-analog validated"
- "Brain confirmed in code"
- "subtle-slice gate proven"

Permitted phrasing:

> Graded falsification with conflict-modulated threshold was tested
> against a subtle-contradiction slice; at the pre-registered
> constants the experiment produced NULL_RESULT (no measurable
> improvement). The infrastructure ships as a falsifiable test bed;
> future re-runs require fresh pre-registration.

## Reproducibility

```bash
PYTHONPATH=. python tools/eai/run_falsifiability_test.py
PYTHONPATH=. pytest tests/eai/protocol/test_graded_falsification.py \
                    tests/eai/protocol/test_graded_gate_threshold.py \
                    tests/eai/calibration/test_falsifiability_v1.py -q
```

Two consecutive runs produce byte-identical reports; the
determinism replay assertion is enforced in the CI workflow.

## Claim boundary

> EAI graded falsification + STN-analog falsifiability test v1
> measures behavioural difference between binary and graded gate
> configurations on a synthetic, pre-registered dataset under
> fixed constants. The current verdict is NULL_RESULT.

This does NOT establish: that EAI replicates basal ganglia
architecture; that graded falsification is preferable to binary;
that the STN-analog hypothesis is true or false. The infrastructure
is a test bed; the verdict is the experiment's primary output.

---

**Pre-registered**: 2026-05-14
**Verdict at commit time**: NULL_RESULT
**Status under CC-META-001 §8.1 ClaimTier**: FALSIFIED only for the specific claim "graded gate, at these constants, improves subtle-slice detection." The engine modification itself is TENTATIVE (synthetic test bed only).
