# Post-Market Surveillance Plan (PMSP)

## Monitoring Objectives
- Detect drift in contradiction-trap pass rate.
- Detect increases in false-promotion rate.
- Detect regression in guardrail revalidation latency.

## Triggers
- Drift alert if rolling false-promotion rate > 0.
- Calibration alert if contradiction benchmark drops below baseline.
- Incident alert for unverifiable external-verification reports.

## Response
1. Freeze promotion path.
2. Route candidates to `QUARANTINED`.
3. Run rollback using latest known-good model/config.
4. Publish incident + corrective action log.
