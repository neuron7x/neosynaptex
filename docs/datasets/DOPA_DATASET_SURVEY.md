# DOPA-CLOSURE — Dataset Survey (DATASET-SCOUT)

Mission: smallest valid dataset that can **falsify or support** the exact claim —
vRPE-gated routing > `uncertainty_only` on VCR under equal budget, advantage gone
under inverted-vRPE. Optimised for fast falsification, not prestige.

## Evaluated datasets

| # | name | source | license | task | labels | N | GT | binary VCR | subjective grading | selected |
|---|------|--------|---------|------|--------|---|----|------------|--------------------|----------|
| 1 | HaluEval | arXiv:2305.11747 / `pminervini/HaluEval` HF | MIT | hallucination recognition (QA/dialogue/summarisation) | hallucinated vs not | 35k | yes | yes (binary) | no, but cheap predictor needs answer generation → LLM | no (needs generator) |
| 2 | TruthfulQA | arXiv:2109.07958 / `truthful_qa` HF | Apache-2.0 | truthfulness QA | MC1/MC2 truthful set | 817 | yes | yes (MC1 binary) | MC mode avoids judge, but item = generative QA | no (first pass) |
| 3 | FEVER | fever.ai / `fever` HF | CC BY-SA 3.0 | claim verification | Supported/Refuted/NEI | 185,445 | yes | yes (drop NEI) | no | candidate |
| 4 | **SciFact** | allenai/scifact (S3 release) | CC BY-NC 2.0 | scientific claim verification w/ evidence | SUPPORT/CONTRADICT/NOINFO | 1.4k claims / 5k corpus | yes | **yes (SUPPORT vs CONTRADICT)** | **no** | **SELECTED** |
| 5 | SciClaimEval 2026 | arXiv (cross-modal) | — | cross-modal sci claim verification | multi | — | yes | partial | yes (multimodal) | no (future branch) |

## Why SciFact for the first death-test

- **Binary correct/incorrect VCR** falls out directly: SUPPORT→1, CONTRADICT→0,
  NOINFO dropped. `VCR = correct_final_labels / total`.
- **No subjective grading, no LLM judge**: claim + cited abstract → label, scored
  against gold annotations.
- **Smallest real dataset that still has true ground truth + evidence**: 505 binary
  train / 188 binary dev items after construction — large enough for a 10-seed
  sweep, small enough to run in seconds and be fully deterministic offline.
- A cheap deterministic predictor exists (TF-IDF + logistic regression); a
  genuinely more expensive verification action exists (bootstrap ensemble),
  giving a real budget axis without any model API.
- FEVER is the documented fallback (same task shape, 185k claims) if SciFact
  signal is degenerate; reserved, not needed.

## Minimal smoke subset

`tests/fixtures/scifact_smoke.jsonl` — 50 deterministically selected items
(25 head of train + 25 tail of dev), text truncated to 1200 chars. Used for the
offline, no-network unit test; the full run uses the local S3 release.

## Risks / contamination

- **License**: SciFact is CC BY-NC 2.0 → research/non-commercial only; dataset is
  git-ignored, never redistributed (only the 50-item smoke fixture, transformed).
- **Leakage**: full abstract (not only gold rationale sentences) is used, so the
  classifier cannot trivially copy the rationale span; train/dev are disjoint and
  the cheap model never sees dev.
- **Class imbalance**: dev ≈ 124 SUPPORT / 64 CONTRADICT (majority-class floor
  ≈ 0.66) — reported explicitly; `cheap_only` and `random_gate` references expose
  any reduction of VCR to plain accuracy or majority voting.
- **Contamination**: SciFact predates and is independent of the DNCA/coherence
  stack; no shared provenance.
