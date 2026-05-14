# EAI Graded Falsification Phase Diagram v1 — Summary

- **schema_version**: `EAI-PHASE-DIAGRAM-v1`
- **total cells**: `20736`
- **verdict**: **`PHASE_REGION_FOUND`**
- **verdict_reason**: separable zones (useful>0 AND regression==0): ['valid/passed', 'expanded/passed', 'contradictory/passed']; co-regression zones: []

## Region totals (global)

| Region | Count |
|---|---:|
| useful | 117 |
| regression | 0 |
| null | 20619 |

## Per-claim-class metrics

| claim_class | total | binary_FPR | graded_FPR | ΔFPR | binary_TPR | graded_TPR | ΔTPR | regression_cells | useful_cells | null_cells |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `true_bounded` | 2592 | 0.0 | 0.0 | 0.0 | 0.333333 | 0.333333 | 0.0 | 0 | 0 | 2592 |
| `false_obvious` | 2592 | 0.111111 | 0.111111 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2592 |
| `false_subtle` | 2592 | 0.333333 | 0.300926 | -0.032407 | 0.0 | 0.0 | 0.0 | 0 | 84 | 2508 |
| `ambiguous` | 2592 | 0.333333 | 0.320602 | -0.012731 | 0.0 | 0.0 | 0.0 | 0 | 33 | 2559 |
| `adversarial_authority` | 2592 | 0.111111 | 0.111111 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2592 |
| `adversarial_boundary_expansion` | 2592 | 0.111111 | 0.111111 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2592 |
| `adversarial_fake_citation` | 2592 | 0.111111 | 0.111111 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2592 |
| `adversarial_software_no_execution` | 2592 | 0.111111 | 0.111111 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2592 |

## Claim boundary

> EAI Graded Falsification Phase Diagram v1 maps the behavioural
> difference between binary and graded gates over a deterministic
> 6-axis synthetic grid. Outputs are diagnostic only; no
> production engine has been modified.
