.PHONY: verify test lint format demo report clean install typecheck reproduce

install:
	pip install -e ".[dev]" --quiet

test: install
	python3 -m pytest tests/ -v --tb=short --timeout=300

lint:
	ruff check neosynaptex.py core/ contracts/ evl/ tests/
	ruff format --check neosynaptex.py core/ contracts/ evl/ tests/

format:
	ruff format neosynaptex.py core/ contracts/ evl/ tests/

typecheck:
	mypy core/ contracts/ --ignore-missing-imports

verify: install lint test
	python3 -c "from core.axioms import SUBSTRATE_GAMMA, gamma_psd, verify_axiom_consistency; gammas=[v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]; subs=[k for k,v in SUBSTRATE_GAMMA.items() if v[0] is not None]; state={'gamma':sum(gammas)/len(gammas),'substrates':subs,'convergence_slope':-0.0016}; assert verify_axiom_consistency(state); print('AXIOM_0: CONSISTENT |', len(subs), 'γ-emitting substrates | γ=' + f'{state[\"gamma\"]:.4f}')"

demo:
	python3 -c "\
from core.axioms import SUBSTRATE_GAMMA, classify_regime; \
print('NFI — Cross-Substrate γ Validation'); \
print('='*50); \
[print(f'{name:20s} γ={gamma:.4f}  |γ-1|={abs(gamma-1.0):.4f}  {classify_regime(gamma)}') for name, (gamma, note) in SUBSTRATE_GAMMA.items() if gamma is not None]; \
[print(f'{name:20s} γ=null   (sub-γ status, ledger v2.0.0: {note[:40]})') for name, (gamma, note) in SUBSTRATE_GAMMA.items() if gamma is None]; \
gammas = [v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]; \
mean_g = sum(gammas)/len(gammas); \
std_g = (sum((g-mean_g)**2 for g in gammas)/len(gammas))**0.5; \
print(f'\nMean: {mean_g:.4f} ± {std_g:.4f} (across {len(gammas)} γ-emitting substrates)'); \
print('AXIOM_0: Intelligence = regime, not substrate.')"

report:
	python3 -c "\
from core.axioms import SUBSTRATE_GAMMA, verify_axiom_consistency; \
gammas = [v[0] for v in SUBSTRATE_GAMMA.values() if v[0] is not None]; \
subs = [k for k, v in SUBSTRATE_GAMMA.items() if v[0] is not None]; \
state = {'gamma': sum(gammas)/len(gammas), 'substrates': subs, 'convergence_slope': -0.0016}; \
result = verify_axiom_consistency(state); \
print(f'NFI STATE: {\"VALID\" if result else \"INVALID\"}'); \
print(f'γ = {state[\"gamma\"]:.4f}'); \
print(f'Substrates: {len(state[\"substrates\"])} γ-emitting witnesses'); \
print(f'Motion: slope={state[\"convergence_slope\"]}')"

reproduce: install
	python3 scripts/reproduce.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info dist build .coverage
