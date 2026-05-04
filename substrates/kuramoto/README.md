# Substrate: kuramoto (TradePulse market substrate)

Substrate class: market microstructure (synthetic and real exchange
data, Kuramoto-oscillator-based indicators).

Verdict per `evidence/replications/registry.yaml`: closely related to
the falsifying record `binance_btcusdt_1h_pilot_2026_04_14`
(γ ≈ 0, r² ≈ 0.001 at hourly resolution). The substrate retains
operational value as a financial backtesting and live-trading toolkit;
it does **not** carry a positive γ ≈ 1 claim under the current canon
(`../../CANONICAL_POSITION.md`).

## Contents

- `adapter.py`-equivalent surfaces — neosynaptex hooks live in
  `src/tradepulse/` and `interfaces/`.
- `src/tradepulse/` — core trading platform code (indicators,
  execution, runtime).
- `core/`, `execution/`, `interfaces/`, `markets/`, `observability/`,
  `analytics/`, `cortex_service/`, `nak_controller/`,
  `neurotrade_pro/`, `tradepulse/` — vendored TradePulse subsystems.
- `infra/`, `deploy/`, `scripts/`, `docs/`, `reports/`, `tests/` —
  the standard TradePulse platform tree.
- `legacy/` — frozen earlier code retained for reference; see
  `legacy/README.md`.
- `UPSTREAM_README.md` — preserved upstream TradePulse README (CLI
  workflow, deployment, full feature index).

## Requirements

Adapter usage from neosynaptex needs only the parent repo dependencies.
The standalone TradePulse system has many additional requirements;
see `UPSTREAM_README.md` and `pyproject.toml` of this directory.

## Usage

Inside neosynaptex, this substrate is exercised by replication runners
at the repo root, including `run_btcusdt_replication.py`.

For the TradePulse standalone CLI / live-trading workflow, see
`UPSTREAM_README.md`.

## Tests

TradePulse ships a large test tree under `tests/` plus performance,
integration, and load suites. Counts are not aggregated into the
parent neosynaptex `tests/` total.

## Output

- Neosynaptex output: γ-pipeline records bound to
  `evidence/gamma_ledger.json` and (for filed replications)
  `evidence/replications/`.
- TradePulse output: backtest reports, live-trading artefacts,
  observability metrics — see upstream README.

## Notes

- "Production-grade", "Enterprise-Grade", "advanced", and similar
  upstream framings are not endorsed at the canon level. The
  γ-program treats this substrate as a market-class example with one
  filed falsification at hourly BTC/USDT resolution; no positive
  cross-substrate convergence is licensed from it.
- Any γ value from this substrate must trace to a registry entry
  under `evidence/replications/` before external citation.
