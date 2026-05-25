# First Customer Execution Plan

`claim_status: hypothesized`

## Purpose

This document converts the strategic value architecture into a concrete first-customer execution path. It is not a valuation narrative. It is a delivery plan for proving whether `neosynaptex` creates measurable value in a real workflow.

## Initial product wedge

The first product wedge is AI research claim review and release governance.

Input:

- an AI-assisted technical claim;
- supporting notes, code, or experiment artifacts;
- optional CI or reproducibility evidence.

Output:

- accepted, rejected, quarantined, falsified, or revise decision;
- evidence map;
- unresolved risk list;
- falsification condition;
- reproducibility packet;
- reviewer-ready audit summary.

## First user profile

The first user is a technical founder, research engineer, AI safety reviewer, applied ML lead, or principal engineer who must decide whether an AI-generated technical claim can be trusted, shipped, revised, or killed.

## Non-goals for the first wedge

- no general-purpose AI assistant positioning;
- no universal intelligence claim;
- no financial valuation claim;
- no broad platform story before a working demo;
- no scientific universality language without evidence.

## Demo scenario

Scenario: A user submits a noisy AI-generated research proposal that claims a new adaptive-system signal.

The system must:

1. extract atomic claims;
2. assign claim status;
3. map each claim to evidence;
4. identify missing evidence;
5. generate falsification tests;
6. classify unresolved risks;
7. produce a final release decision;
8. export an audit packet.

## Minimum viable demo requirements

A demo is acceptable only if it can be run by one command and produces deterministic output.

Required artifacts:

- input example under `examples/first_customer/`;
- expected output packet under `proof_bundle/first_customer_demo/`;
- command in Makefile;
- JSON output;
- Markdown executive summary;
- claim/evidence table;
- unresolved risk table;
- deterministic hash of the output packet.

## Acceptance criteria

The first-customer demo passes only if:

- the command exits with code `0` on valid input;
- malformed input exits non-zero;
- every accepted claim has evidence;
- every unsupported claim is quarantined or rejected;
- every promoted decision has a falsification boundary;
- the output is deterministic across two repeated runs;
- the report is understandable without reading repository internals.

## Baseline comparison

The first measurable benchmark compares three modes:

1. manual review;
2. unstructured LLM-only review;
3. `neosynaptex` claim-governance review.

Measured outcomes:

- review time;
- number of unsupported claims caught;
- number of missing evidence links found;
- reproducibility defects detected;
- reviewer confidence after audit.

## Instrumentation

Every demo run should emit:

```yaml
run_id: ""
timestamp_utc: ""
input_hash: ""
output_hash: ""
claim_count: 0
accepted_claims: 0
rejected_claims: 0
quarantined_claims: 0
falsification_tests: 0
missing_evidence_items: 0
runtime_seconds: 0.0
```

## 14-day execution backlog

### Day 1-2: Demo contract

- define input schema;
- define output schema;
- create one representative example;
- define invalid-input fixture.

### Day 3-5: Claim extraction and status mapping

- implement deterministic parser;
- map claims to statuses;
- fail closed on unsupported status;
- add unit tests.

### Day 6-8: Evidence and risk mapping

- link claims to artifacts;
- detect missing evidence;
- classify risk severity;
- generate risk table.

### Day 9-10: Falsification generator

- create falsification condition per promoted claim;
- require boundary text;
- block promotion when boundary is missing.

### Day 11-12: Report packet

- emit JSON;
- emit Markdown;
- compute hash;
- add deterministic rerun test.

### Day 13-14: Demo packaging

- add Makefile target;
- add README snippet;
- add acceptance test;
- update PR body with measured demo command once implemented.

## Promotion gate

Strategic positioning may be promoted only after the first demo produces measured output and the acceptance criteria pass in CI.

Until then, strategic value remains a hypothesis.
