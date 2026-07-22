# Traceability Matrix

| Requirement or claim | Status | Implementation evidence | Test or artifact evidence | Gap |
|---|---|---|---|---|
| Generate reproducible retail-like daily demand | Implemented | `src/perishable_lab/data/synthetic.py` | `tests/test_synthetic_data.py`, `reports/example_run/forecast_metrics.json` | Synthetic only; no external benchmark committed. |
| Validate one row per date, store, and product | Implemented | `src/perishable_lab/data/validation.py`, `src/perishable_lab/data/canonical.py` | `tests/test_synthetic_data.py`, `tests/test_retail_adapter.py` | Real source-specific anomaly catalog is not implemented. |
| Represent retail source contracts | Partially implemented | `src/perishable_lab/data/contracts.py`, `src/perishable_lab/data/adapters.py` | `tests/test_retail_adapter.py` | Contracts are local Python models; warehouse enforcement is illustrative. |
| Preserve product lineage and effective dating | Partially implemented | `src/perishable_lab/data/canonical.py` | `tests/test_retail_adapter.py` | No persisted identity graph or remap audit artifact. |
| Use only information available by decision cutoff | Partially implemented | `src/perishable_lab/data/canonical.py`, `src/perishable_lab/features.py` | `tests/test_retail_adapter.py`, `tests/test_features.py` | Feature availability is not represented as a versioned contract. |
| Build lag, rolling, calendar, price, promotion, and inventory features | Implemented for local batch mode | `src/perishable_lab/features.py` | `tests/test_features.py` | Store/product codes are not persisted for scoring parity. |
| Split train, calibration, and test windows chronologically | Implemented | `src/perishable_lab/evaluation/splits.py`, `src/perishable_lab/pipelines/demo.py` | `tests/test_pipeline.py` | Rolling-origin evaluation exists as utility but is not used by default demo. |
| Fit probabilistic demand forecasts | Implemented baseline | `src/perishable_lab/forecasting/quantile.py` | `tests/test_forecasting_horizon.py`, `reports/example_run/forecast_metrics.json` | No hierarchical or joint lead-time distribution model. |
| Prevent non-monotone quantile outputs | Implemented | `src/perishable_lab/forecasting/quantile.py` | `tests/test_forecasting_horizon.py` | None for baseline model. |
| Calibrate forecast intervals | Partially implemented | `src/perishable_lab/forecasting/conformal.py` | `tests/test_conformal.py`, `reports/example_run/calibration.png` | Global only; no segment-level acceptance gate. |
| Approximate cumulative lead-time demand | Partially implemented | `src/perishable_lab/forecasting/horizon.py` | `tests/test_forecasting_horizon.py` | Assumes approximate independent daily quantiles; no validation against simulated or empirical multi-day demand. |
| Handle intermittent and cold-start demand | Partially implemented | `src/perishable_lab/forecasting/baselines.py` | `tests/test_forecasting_horizon.py` | Fallback is not integrated into production scoring policy selection. |
| Simulate FIFO perishable inventory | Implemented | `src/perishable_lab/inventory/simulator.py` | `tests/test_inventory.py` | Event-order mode is fixed. |
| Distinguish physical and recorded inventory | Implemented | `src/perishable_lab/inventory/simulator.py` | `tests/test_inventory.py` | No Bayesian or filtering estimator for hidden inventory state. |
| Model pending deliveries and lead-time variation | Implemented local controls | `src/perishable_lab/inventory/simulator.py` | `tests/test_inventory.py` | Supplier reliability is synthetic/configured, not estimated from data. |
| Enforce order constraints | Implemented | `src/perishable_lab/inventory/policies.py`, `src/perishable_lab/inventory/simulator.py` | `tests/test_inventory.py` | No optimization over multiple future periods. |
| Compare ordering policies on business metrics | Implemented | `src/perishable_lab/pipelines/demo.py`, `src/perishable_lab/inventory/simulator.py` | `reports/example_run/policy_metrics.csv`, `reports/example_results.md` | Selection does not enforce service floors by segment. |
| Separate statistical and decision metrics | Implemented | `src/perishable_lab/forecasting/metrics.py`, `src/perishable_lab/evaluation/reporting.py` | `reports/example_results.md`, `tests/test_pipeline.py` | Segment views are absent. |
| Build monitoring report | Implemented basic checks | `src/perishable_lab/monitoring/quality.py` | `tests/test_monitoring.py`, `reports/example_run/monitoring_report.json` | Limited alert types and no runbook link per alert. |
| Persist run metadata | Implemented for demo outputs | `src/perishable_lab/pipelines/demo.py` | `tests/test_pipeline.py`, generated CSV outputs | No central manifest schema beyond output columns. |
| Provide GCP helper utilities | Implemented utility level | `src/perishable_lab/deployment/gcp.py` | `tests/test_deployment.py` | No live project integration proof. |
| Provide dbt BigQuery models | Scaffold only | `dbt_project/models/` | None committed from dbt execution | Add dbt parse/build validation in CI. |
| Provide Airflow orchestration | Scaffold only | `airflow/dags/perishable_decision_pipeline.py` | None | DAG is not loaded or tested in CI. |
| Provide Cloud Build and Cloud Run job pattern | Scaffold only | `gcp/cloudbuild.yaml`, `gcp/README.md`, `gcp/DEPLOYMENT_RUNBOOK.md` | `tests/test_deployment.py` covers helper functions | Missing IAM, environment, and deployment verification. |
| Build and test in CI | Implemented | `.github/workflows/ci.yml`, `Dockerfile` | GitHub workflow definition | dbt and Airflow checks are not included. |
| Keep portfolio claims evidence-based | Partially implemented | `README.md`, `docs/CASE_STUDY.md`, `docs/INTERVIEW_WALKTHROUGH.md`, `docs/READINESS_REVIEW.md` | `reports/example_run/` | Needs continued review as new capabilities are added. |

## Local Instruction Set Coverage

The numbered local files cover repository setup, data contracts, forecasting, simulation, policy evaluation, GCP deployment, readiness review, demo preparation, audit, data quality, stockout handling, product identity, hierarchical forecasting, promotions, shelf life, supplier reliability, hidden inventory state, simulator validation, stochastic optimization, business-cost estimation, forecast-to-decision integration, offline evaluation, rollout, feature store correctness, batch publication, assurance, observability, governance, documentation cards, operations discovery, dashboards, portfolio narrative, interview materials, case study, failure taxonomy, public dataset benchmarking, advanced models, workflow safeguards, and final release audit.

Items `00` through `08` are represented by committed code and docs. This audit begins the remaining delivery sequence with an evidence-based roadmap and issue-ready backlog.
