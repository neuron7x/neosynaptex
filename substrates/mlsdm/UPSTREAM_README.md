# MLSDM (Multi-Level Synaptic Dynamic Memory)

![MLSDM Hero](assets/mlsdm-hero.svg)

[![CI Smoke Tests](https://github.com/neuron7xLab/mlsdm/actions/workflows/ci-smoke.yml/badge.svg)](https://github.com/neuron7xLab/mlsdm/actions/workflows/ci-smoke.yml)
[![Production Gate](https://github.com/neuron7xLab/mlsdm/actions/workflows/prod-gate.yml/badge.svg)](https://github.com/neuron7xLab/mlsdm/actions/workflows/prod-gate.yml)
[![Performance & Resilience](https://github.com/neuron7xLab/mlsdm/actions/workflows/perf-resilience.yml/badge.svg)](https://github.com/neuron7xLab/mlsdm/actions/workflows/perf-resilience.yml)
[![Property-Based Tests](https://github.com/neuron7xLab/mlsdm/actions/workflows/property-tests.yml/badge.svg)](https://github.com/neuron7xLab/mlsdm/actions/workflows/property-tests.yml)
[![SAST Security Scan](https://github.com/neuron7xLab/mlsdm/actions/workflows/sast-scan.yml/badge.svg)](https://github.com/neuron7xLab/mlsdm/actions/workflows/sast-scan.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Is

MLSDM is a production-ready, neurobiologically-grounded cognitive architecture with moral governance. It provides a governed cognitive memory system with a circadian wake/sleep rhythm, multi-level memory (L1/L2/L3), moral filtering, and aphasia detection. The system exposes an HTTP API, a Python library, and a CLI entrypoint for integration with LLM applications.

## Interfaces

### Python Library

```python
from mlsdm import create_llm_wrapper

wrapper = create_llm_wrapper(
    wake_duration=8,
    sleep_duration=3,
    initial_moral_threshold=0.5,
)
result = wrapper.generate(prompt="Hello", moral_value=0.8)
```

### HTTP API

The HTTP API is served via FastAPI with interactive docs at `/docs` and `/redoc`.

**Endpoints:**
- `POST /generate` — Generate governed response
- `POST /infer` — Extended inference with governance options
- `GET /health` — Simple health check
- `GET /health/live` — Liveness probe
- `GET /health/ready` — Readiness probe
- `GET /status` — Extended service status

### CLI

```bash
mlsdm info      # Show version, status, and configuration
mlsdm serve     # Start the HTTP API server
mlsdm demo -i   # Interactive demo
mlsdm check     # Check environment and configuration
mlsdm eval      # Run evaluation scenarios
```

## Quick Start

### Install

```bash
# Using uv (recommended, uses uv.lock)
uv sync

# Or using pip
pip install -e .
```

### Start the Server

```bash
mlsdm serve --host 0.0.0.0 --port 8000
```

### API Usage

```bash
# Health check
curl http://localhost:8000/health

# Generate a governed response
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how are you?"}'
```

## Verified Contracts & Evidence

Authoritative, evidence-backed contracts:

- [docs/CONTRACTS_CRITICAL_SUBSYSTEMS.md](docs/CONTRACTS_CRITICAL_SUBSYSTEMS.md) — Critical subsystem contracts
- [docs/CLAIM_EVIDENCE_LEDGER.md](docs/CLAIM_EVIDENCE_LEDGER.md) — Claim-to-evidence mapping

**Verification commands:**

```bash
make verify-docs           # Verify documentation contracts against code
make verify-security-skip  # Verify security skip path invariants
```

Evidence snapshots are produced by the `readiness-evidence.yml` workflow and stored under `artifacts/evidence/`.

## Quality Gates (CI Parity)

These commands match what CI runs:

```bash
make lint           # Run ruff linter on src and tests
make type           # Run mypy type checker on src/mlsdm
make test           # Run all tests (uses pytest.ini config)
make test-fast      # Run fast unit tests (excludes slow/comprehensive)
make coverage-gate  # Run coverage gate (default threshold: 75%)
```

The `coverage_gate.sh` script enforces the coverage threshold (default `COVERAGE_MIN=75`).

## Documentation

Full documentation is available in the [docs/index.md](docs/index.md).

**Key Documents:**
- [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md) — Detailed usage examples and best practices
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — Complete API documentation
- [docs/ARCHITECTURE_SPEC.md](docs/ARCHITECTURE_SPEC.md) — System architecture
- [docs/CONFIGURATION_GUIDE.md](docs/CONFIGURATION_GUIDE.md) — Configuration reference
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) — Production deployment patterns
- [docs/SECURITY_POLICY.md](docs/SECURITY_POLICY.md) — Security guidelines

**Readiness Status:**
- [docs/status/READINESS.md](docs/status/READINESS.md) — Canonical readiness truth

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
