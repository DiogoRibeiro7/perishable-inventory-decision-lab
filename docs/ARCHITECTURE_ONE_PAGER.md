# Architecture One-Pager

## Purpose

Convert uncertain fresh-food demand into auditable replenishment recommendations while measuring the tradeoff between availability, waste, lost sales, inventory, and operating cost.

## Flow

```text
source contracts
  -> canonical daily demand table
  -> feature builder with decision-time cutoffs
  -> quantile forecaster
  -> interval calibration and forecast metrics
  -> order policy
  -> FIFO perishable simulator
  -> policy metrics, monitoring, and run manifest
```

## Core boundaries

- `src/perishable_lab/data`: source contracts, synthetic generation, validation, and public benchmark adapter.
- `src/perishable_lab/forecasting`: probabilistic baselines, calibration, lead-time aggregation, and research comparison.
- `src/perishable_lab/inventory`: simulator, policy rules, reconciliation, and constraints.
- `src/perishable_lab/monitoring`: data, forecast, and decision health checks.
- `src/perishable_lab/publication.py`: recommendation validation and local atomic publication.
- `dbt_project`, `airflow`, and `gcp`: example batch deployment pattern.

## Design choices

- Forecast and policy metrics are separated because a better statistical score can still produce a worse order.
- Run manifests are immutable evidence for reproducibility.
- Synthetic data is used for repeatable tests; field validation is a separate phase.
- Deployment examples keep batch scoring idempotent and partitioned by business date.
