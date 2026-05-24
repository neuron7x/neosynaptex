# DOPA-CLOSURE v2 Patch Plan (new PR)

1. Land construct contract and ADR.
2. Land SSOT allocator YAML and result schema.
3. Land runtime allocator with inverted-U gate and budget ledger.
4. Land contract validator script.
5. Land full-path acceptance tests (allocator + schema + contract + controls presence).
6. Generate evidence ledger artifact at `evidence/dopa_closure_v2/budget_ledger.json`.
7. Wire CI job in follow-up if repository policy requires separate workflow approval.
