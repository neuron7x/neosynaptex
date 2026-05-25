# Machine Thinking Capital Playbook

## Objective
Transform checklist discipline into **engineering capital**: reusable reliability, lower defect burn, faster governance approvals, and better decision quality.

## Capital metrics emitted by validator
- `completion_ratio` — execution closure.
- `value_score` — epistemic closure weighted toward high-risk sections.
- `capital_index` — composite operational value signal (0..1).

## Governance intents
1. **Intent: prevent cosmetic progress**
   - Gate on `capital_index >= 0.75` for release candidate branches.
2. **Intent: prioritize expensive risk first**
   - Use `intention_hints` to close highest weighted unresolved sections first.
3. **Intent: reduce cycle time without quality collapse**
   - Use `basic --min-completion 0.6 --min-capital-index 0.55` for draft phases;
     escalate to strict `research_v1` before merge.

## Suggested maturity ladder
- Draft: `basic`, moderate thresholds.
- Pre-merge: `research_v1`, full completion.
- Release: `research_v1` + `min_capital_index >= 0.9`.

## One-command usage
```bash
python substrates/bn_syn/scripts/validate_thinking_checklist.py \
  --checklist substrates/bn_syn/docs/MACHINE_THINKING_SHOWCASE_CHECKLIST.md \
  --profile research_v1 \
  --min-capital-index 0.9 \
  --json-out proof_bundle/reports/thinking_capital_report.json
```


## Product mode (one command)

```bash
make thinking_product_report
```

This command is fail-closed and creates both machine JSON and executive Markdown artifacts in `proof_bundle/reports/` for immediate governance use.
