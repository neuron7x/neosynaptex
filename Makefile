.PHONY: all clean lock sync_locked init validate_contracts test_dynamic verify verify_pr verify_full audit_internal governance_brake unicode_scan secrets_scan sast dependency_audit sbom security package_manifest package_scan test lint format install typecheck reproduce report demo demo_full demo_synthetic_ci

PR_BODY_FILE ?= /tmp/pr_body.txt
PYTHON ?= python3

all: clean sync_locked governance_brake validate_contracts unicode_scan secrets_scan sast dependency_audit sbom package_manifest package_scan test_dynamic audit_internal

clean:
	@echo "Purging non-deterministic artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info dist build .coverage htmlcov .tox .nox

lock:
	uv lock

sync_locked:
	uv sync --locked --extra test --extra dev --extra security

init:
	@echo "Bootstrapping hermetic environment via uv..."
	uv sync --locked --extra test --extra dev

validate_contracts:
	@echo "Parsing invariants.yaml and enforcing traceability..."
	uv run python3 scripts/validate_invariants.py
	uv run ruff check neosynaptex.py core/ contracts/ evl/ tests/


governance_brake:
	@echo "Checking PR-body claim_status contract from explicit event input..."
	@if [ -n "$${PR_BODY:-}" ]; then \
		mkdir -p "$$(dirname "$(PR_BODY_FILE)")"; \
		printf '%s' "$${PR_BODY}" > "$(PR_BODY_FILE)"; \
	elif [ -n "$${GITHUB_EVENT_PATH:-}" ] && [ -f "$${GITHUB_EVENT_PATH}" ]; then \
		uv run python -c "import json, os, pathlib; p=pathlib.Path('$(PR_BODY_FILE)'); p.parent.mkdir(parents=True, exist_ok=True); data=json.load(open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8')); p.write_text((data.get('pull_request') or {}).get('body') or '', encoding='utf-8')"; \
	fi
	@test -s "$(PR_BODY_FILE)"
	uv run python -m tools.audit.pr_body_check "$(PR_BODY_FILE)"

test_dynamic:
	@echo "Executing property-based test matrix..."
	uv run pytest --hypothesis-show-statistics --cov=core --cov-fail-under=95 tests/

install:
	uv sync --locked --extra test --extra dev

test: install
	uv run python3 -m pytest tests/ -v --tb=short --timeout=300

lint:
	uv run ruff check neosynaptex.py core/ contracts/ evl/ tests/
	uv run ruff format --check neosynaptex.py core/ contracts/ evl/ tests/

format:
	uv run ruff format neosynaptex.py core/ contracts/ evl/ tests/

typecheck:
	uv run mypy core/ contracts/ --ignore-missing-imports

verify_pr: install lint test
	uv run python3 -c "from core.axioms import SUBSTRATE_GAMMA, verify_axiom_consistency; gammas=[v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]; subs=[k for k,v in SUBSTRATE_GAMMA.items() if v[0] is not None]; state={'gamma':sum(gammas)/len(gammas),'substrates':subs,'convergence_slope':-0.0016}; assert verify_axiom_consistency(state); print('AXIOM_0: CONSISTENT')"

reproduce: install
	uv run python3 scripts/reproduce.py

demo_full:
	$(PYTHON) demo_multi.py

demo_synthetic_ci:
	NEOSYNAPTEX_DEMO_SYNTHETIC_ONLY=1 $(PYTHON) demo_multi.py

demo: demo_synthetic_ci

report:
	uv run python3 run_calibration_diagnostic.py
verify_full: install lint test
	uv run python3 -c "from core.axioms import SUBSTRATE_GAMMA, verify_axiom_consistency; gammas=[v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]; subs=[k for k,v in SUBSTRATE_GAMMA.items() if v[0] is not None]; state={'gamma':sum(gammas)/len(gammas),'substrates':subs,'convergence_slope':-0.0016}; assert verify_axiom_consistency(state); print('AXIOM_0: CONSISTENT')"

verify: verify_full

audit_internal: validate_contracts package_scan
	NFI_FAIL_CLOSED=1 uv run python scripts/validate_invariants.py
	@echo "Internal audit surfaces executed (contracts + package evidence scan)."


unicode_scan:
	mkdir -p artifacts/security
	uv run python scripts/security/unicode_safety_check.py | tee artifacts/security/unicode_scan.txt

secrets_scan:
	mkdir -p artifacts/security
	uv run python scripts/security/release_secret_safety_check.py

sast:
	mkdir -p artifacts/security
	uv run bandit -r core contracts scripts neosynaptex.py -f json -o artifacts/security/bandit.json

dependency_audit:
	mkdir -p artifacts/security
	uv run pip-audit -f json -o artifacts/security/pip_audit.json

sbom:
	mkdir -p artifacts/sbom
	uv export --format requirements-txt --locked > artifacts/sbom/requirements.locked.txt

security: unicode_scan secrets_scan sast dependency_audit sbom

package_manifest:
	mkdir -p artifacts/package
	uv run python scripts/security/package_evidence_manifest.py

package_scan:
	mkdir -p artifacts/package
	uv run python scripts/security/evidence_leakage_scan.py
