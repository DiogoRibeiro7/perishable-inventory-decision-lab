# Perishable Inventory Decision Lab

A production-oriented portfolio project for **probabilistic demand forecasting, perishable inventory simulation, and ordering-policy optimisation**.

The project models a fresh-grocery decision system in which demand is uncertain, products expire, inventory records are imperfect, and every order trades off waste against availability. It is deliberately designed as an end-to-end decision system rather than a forecasting notebook.

## What this repository demonstrates

- Distributional forecasting with quantile gradient boosting.
- Split-conformal calibration and empirical coverage monitoring.
- A cohort-based perishable inventory simulator.
- Newsvendor and base-stock ordering policies.
- Rolling-origin backtesting with both forecast and operational metrics.
- Data-quality and model-degradation checks.
- Production Python, typed interfaces, tests, linting, containers, and CI.
- Example dbt, Airflow, BigQuery, Cloud Run, and model-registry integration patterns.

## Decision objective

For each store-product-day, choose an order quantity that minimises expected operating cost:

\[
C = c_w \cdot \text{waste} + c_s \cdot \text{lost sales} + c_h \cdot \text{ending inventory}
\]

subject to uncertain demand, shelf life, delivery lead time, shrinkage, and noisy stock records. The model therefore optimises a **business decision**, not only a statistical score.

## Repository map

```text
src/perishable_lab/
├── data/              # Synthetic grocery data and validation
├── forecasting/       # Quantile model, conformal calibration, metrics
├── inventory/         # Perishable simulator and ordering policies
├── evaluation/        # Time-based backtesting
├── monitoring/        # Data and forecast health checks
├── pipelines/         # End-to-end training and evaluation workflow
└── cli.py              # Reproducible command-line entry point

airflow/               # Example orchestration DAG
dbt_project/           # Example BigQuery/dbt transformations
gcp/                   # Cloud Build and Cloud Run Job deployment examples
docs/                   # Architecture, modelling choices, and case-study narrative
tests/                  # Unit and integration tests
```

## Run locally

Requirements: Python 3.11 or 3.12 and Poetry.

```bash
poetry install
poetry run perishable-lab demo --output-dir artifacts/demo
```

The command generates data, trains quantile models, conformalises the prediction interval, evaluates forecast quality, runs three inventory policies, and writes:

```text
artifacts/demo/
├── synthetic_daily_demand.csv
├── forecast_predictions.csv
├── forecast_metrics.json
├── policy_metrics.csv
├── monitoring_report.json
└── run_manifest.json
```

Run quality checks:

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy src
```

## Example experiments

```bash
# Larger simulation
poetry run perishable-lab demo \
  --days 365 \
  --stores 8 \
  --products 30 \
  --seed 42 \
  --output-dir artifacts/year_run

# Compare policies at different target service levels
poetry run perishable-lab demo --service-level 0.80 --output-dir artifacts/sl80
poetry run perishable-lab demo --service-level 0.95 --output-dir artifacts/sl95
```

## Core metrics

Forecasting:

- Pinball loss by quantile.
- Empirical interval coverage.
- Mean interval width.
- Weighted interval score.
- Approximate CRPS from quantile losses.

Operations:

- Fill rate and on-shelf availability proxy.
- Waste rate.
- Lost-sales rate.
- Average stock and order quantity.
- Total and per-unit decision cost.
- Policy regret relative to a clairvoyant lower-bound benchmark.

## Why synthetic data is appropriate here

Real retailer data is commercially sensitive and usually unavailable. A controlled generator makes the assumptions explicit and permits stress tests that are difficult to construct from a single public dataset. The data layer is isolated behind a contract, so a public or private retailer dataset can be added without changing the forecasting and inventory interfaces.

See [`docs/ROLE_ALIGNMENT.md`](docs/ROLE_ALIGNMENT.md) for the exact mapping between this repository and the target role, and [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) for a concise interview walkthrough.
