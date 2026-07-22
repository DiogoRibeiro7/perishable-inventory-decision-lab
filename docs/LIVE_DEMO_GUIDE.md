# Live Demo Guide

Target length: 10 minutes.

## Setup

Start from a clean checkout:

```bash
poetry install
poetry run perishable-lab demo --days 90 --stores 2 --products 4 --seed 42 --output-dir artifacts/release-demo-check
```

If local execution fails because dependencies or shell access are unavailable, continue from the committed artifacts in [`reports/example_run`](../reports/example_run) and the interpretation in [`reports/example_results.md`](../reports/example_results.md).

## Walkthrough

1. Open the README and frame the project as a decision system, not a forecast-only notebook.
2. Show the generated `run_manifest.json` and point out package version, config hash, model version, policy version, and artifact list.
3. Show `forecast_metrics.json` and `calibration.png` from the committed example run. Explain that interval coverage is the contract between forecast uncertainty and downstream ordering.
4. Show `policy_metrics.csv` and `policy_frontier.png`. Compare availability, waste, lost sales, and cost per demand unit.
5. Use `src/perishable_lab/demand_censoring/strategies.py` and `tests/test_demand_censoring.py` to explain how observed sales can understate latent demand during stockouts.
6. Use `src/perishable_lab/inventory/reconciliation.py` and `tests/test_inventory_reconciliation.py` to explain why stock-record noise changes order quality.
7. Use `src/perishable_lab/decision.py` and [`docs/FORECAST_DECISION_CONTRACT.md`](FORECAST_DECISION_CONTRACT.md) to explain how a forecast distribution becomes an order quantity.
8. End with [`docs/FINAL_RELEASE_AUDIT.md`](FINAL_RELEASE_AUDIT.md) and show that synthetic limits are documented instead of hidden.

## Required examples

| Example | Where to show it |
|---|---|
| Normal run | `artifacts/release-demo-check/run_manifest.json` after the command above |
| Stockout-censoring case | `tests/test_demand_censoring.py` |
| Inventory-record-error case | `tests/test_inventory_reconciliation.py` |
| Waste versus service tradeoff | `reports/example_run/policy_frontier.png` |
| Recommendation explanation | `docs/FORECAST_DECISION_CONTRACT.md` and `src/perishable_lab/decision.py` |

## Fallback path

The presentation can continue without cloud access or live training by using committed artifacts:

- [`reports/example_results.md`](../reports/example_results.md)
- [`reports/example_run/forecast_metrics.json`](../reports/example_run/forecast_metrics.json)
- [`reports/example_run/policy_metrics.csv`](../reports/example_run/policy_metrics.csv)
- [`docs/MODEL_CARD.md`](MODEL_CARD.md)
- [`docs/POLICY_CARD.md`](POLICY_CARD.md)
- [`docs/SIMULATOR_CARD.md`](SIMULATOR_CARD.md)
