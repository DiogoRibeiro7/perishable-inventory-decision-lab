# Role Alignment

This repository is intentionally scoped to the central technical and operational requirements of a senior data scientist working on fresh-food ordering.

| Role requirement | Repository evidence |
|---|---|
| Distributional and probabilistic forecasting | Quantile gradient boosting, non-crossing correction, conformal calibration, pinball loss, interval score, and coverage monitoring. |
| Inventory simulation | Cohort-level stock with shelf life, expiry, FIFO fulfilment, delivery lead time, shrinkage, and noisy inventory observations. |
| Ordering-policy design | Median baseline, fixed service-level base-stock policy, and product-specific economic newsvendor critical fractiles. |
| Decisions under uncertainty | Forecast distributions are converted into order quantities and evaluated using waste, availability, lost sales, and total operating cost. |
| Backtesting and monitoring | Contiguous temporal splits, rolling-origin utilities, data-contract checks, coverage alerts, and persisted run manifests. |
| Production-quality Python | Typed package, Pydantic configuration, modular interfaces, tests, linting, type checking, Docker, and GitHub Actions. |
| Python and SQL | Python implementation plus dbt/BigQuery staging and decision marts. |
| GCP, dbt, and orchestration | Cloud Build, Cloud Run Job deployment, BigQuery-oriented dbt models, and an Airflow DAG. |
| Cross-functional communication | Architecture and modelling documents explain assumptions, operational trade-offs, limitations, and decisions in non-academic language. |

## Deliberate scope choices

The repository does not pretend to reproduce a retailer's production environment. It provides an auditable decision-system core with explicit extension points for real point-of-sale, stock, waste, product-master, promotion, and order data.

The model is one-step-ahead by design. The next meaningful extension is a multi-horizon demand distribution that directly represents cumulative lead-time demand.
