# State Transition Transparency Map

```text
CANDIDATE
  ├─(falsification pass + boundary valid)──> EVIDENCE ──> INTEGRATION_MEMORY
  ├─(falsification fail)───────────────────> KILLED ───> GUARDRAIL_REGISTRY
  └─(insufficient evidence / ambiguity)────> QUARANTINED -> OPEN_QUESTIONS_QUEUE

EVIDENCE x MATCHED_GUARDRAIL -> REVALIDATION_GATE -> REVALIDATION_ARTIFACT
REVALIDATION_ARTIFACT -> {SCOPED_DOWN | RETIRED | SUPERSEDED | STRENGTHENED | UNCHANGED}
```

This map is normative for the EAI lifecycle and should match protocol tests.
