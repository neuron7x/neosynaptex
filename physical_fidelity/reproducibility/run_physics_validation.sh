#!/usr/bin/env bash
# NFI-PROMPT-002 full physics validation pipeline (solo-operator, local hardware).
# Runs baseline -> falsifiable suite -> oracle, archiving artifacts with a stamp.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
STAMP="${1:-latest}"
OUT="physical_fidelity/artifacts/physics_validation/${STAMP}"
mkdir -p "$OUT"

echo "[1/4] falsifiable + adversarial suite"
python -m pytest physical_fidelity/tests/ -q | tee "$OUT/pytest.log"

echo "[2/4] reference apparatus baseline (S0)"
python -m physical_fidelity.pf.baseline | tee "$OUT/baseline.json"

echo "[3/4] 10-axis scoring oracle (S_total)"
python -m physical_fidelity.physics_score | tee "$OUT/score.json"

echo "[4/4] quality gates"
ruff check physical_fidelity/ && ruff format --check physical_fidelity/
mypy physical_fidelity/pf/ physical_fidelity/physics_score.py --ignore-missing-imports

echo "DONE -> $OUT"
