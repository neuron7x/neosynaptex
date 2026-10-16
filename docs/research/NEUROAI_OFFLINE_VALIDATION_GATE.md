# NEUROAI Offline Validation Gate v1

**Purpose:** create concrete execution evidence when GitHub Actions is unavailable.
**Entry point:** `scripts/verify_neuroai_offline.py`.
**Trust boundary:** tests prove only the executed code/invariants in the recorded
environment; they do not prove biological plausibility, truthful LLM reasoning,
production security or the benefit of DNCA modulation.

## Run

From a clean checkout of `neuron7x/neosynaptex`, with development dependencies
installed:

```bash
python -m pip install -e '.[dev]' -e agents
python scripts/verify_neuroai_offline.py --timeout 240
```

By default the evidence goes to a newly created unique directory under the
operating-system temporary folder. To specify an outside-repository
destination, use:

```bash
python scripts/verify_neuroai_offline.py \
  --output-dir /tmp/neosynaptex-evidence-run-001 \
  --timeout 240
```

The destination **must not already exist**, to prevent overwriting evidence.

## Fail-closed conditions

The top-level verdict is `PASS` only if all conditions hold:

1. `git rev-parse HEAD` succeeds and a commit SHA is recorded.
2. `git status --porcelain --untracked-files=all` reports a clean tree
   before tests start.
3. All pinned research source/test/configuration files exist as regular
   non-symlink files and are hashed using SHA-256.
4. Python compileall exits zero.
5. The complete DOPA test subtree passes pytest.
6. A separate **mandatory-test** stage runs the core fail-closed security,
   arithmetic verifier, HMAC attestation, negative-control and offline-runner
   tests; an independently parsed JUnit XML must contain at least one actual
   testcase and **zero skipped, failed or errored testcases**. Six
   named security-critical tests must appear in that JUnit evidence,
   preventing a partial or selectively deselected suite from passing.
   `PYTEST_ADDOPTS` and `PYTEST_PLUGINS` are removed from the subprocess
   environment to prevent silent selection/plugin injection.
7. Ruff completes with exit code zero for the pinned security-critical files.
8. Mypy completes with exit code zero for the pinned independent verification
   modules.
9. Every hashed source (including this runner and pyproject.toml) remains
   unchanged **after** the tool invocations, and Git HEAD and worktree remain
   stable and clean.
10. All emitted stage logs retain the SHA-256 recorded by the runner; the
    mandatory JUnit report is also included by SHA-256.
11. None of the tools is missing, timed out, or crashed.

Command arguments are fixed: subprocesses run without `shell=True`. The
script never converts a missing tool or a skipped stage into success. Logs for
every stage and their SHA-256 hashes are exported alongside `evidence.json`.

The complete log is a decoded stdout/stderr capture; Python can replace
invalid UTF-8 sequences. This is execution-level reproducibility information,
not a byte-identical cryptographically signed remote attestation.

**H2 hardening (2026-10-16):** `source_sha256_post`,
`postflight_blockers`, `mandatory_test_summary` and
`mandatory_test_junit_sha256` prevent a passing report from silently
ignoring an omitted/skipped mandatory testcase, changed source, changed Git
HEAD, dirty worktree or modified tool logs. General-suite optional skips
remain visible in its raw log; mandatory security tests cannot skip.

## Output contract

`evidence.json` includes: protocol version, timestamp UTC, Git SHA, Python
version, platform, source manifest hashes, preflight blockers, stage arguments,
exit codes, stage PASS/FAIL states and log hashes, and overall PASS/FAIL.
No secret environment variables are written to the manifest.

The SHA-256 manifest is a diagnostic **content binding** only. Anyone with
write permission to both logs and hashes can forge a consistent record; a
higher assurance system would sign externally and store the result in an
independently controlled append-only store.

## Scope and limitations

- Tests and tool metadata are meaningful *only after a real local execution*.
  GitHub Actions returned failed jobs with no reported steps; job-log downloads
  returned unavailable artifact errors. This is **not evidence** of a failing
  or passing local test suite. Running and archiving this gate is required.
- A clean Git tree does not guarantee fixed Docker images, library wheels,
  microcode, GPU determinism, or network fixture immutability.
- The runner pins which checks are requested, not their tool versions.
  Capture a separate locked dependency environment and use an isolated
  container for cross-machine reproducibility.
- `ruff` and `mypy` cover specified critical paths, not the entire very
  large research monorepo. Do not call the output a universal repository audit.
- Python `compileall` checks syntax, not behavioral correctness.
- Local execution by the same actor who authored code is not independent
  replication. A second reviewer should repeat the instructions and compare
  the report and code hashes.

## Promotion

`MERGED` is a source-control state. `PASS` is a local tool-execution state.
`INSTRUMENT_ADMISSIBLE` requires verified constructs and a real external
verifier. `EMPIRICALLY_SUPPORTED` requires qualified held-out evidence,
budget-matched baselines, confidence intervals and independent replication.
None implies the next automatically.

**⊛ Operational invariant:** missing tests are failures of knowledge, not
silent successes.
