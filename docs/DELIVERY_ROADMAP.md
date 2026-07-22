# Delivery Roadmap

## Principles

- Correctness before model complexity.
- Every milestone must produce an executable end-to-end increment.
- Existing public package boundaries should remain stable unless the milestone explicitly names a migration.
- Rollback must preserve the current local demo path: `poetry run perishable-lab demo`.

## Milestone 1: Censored Demand And Stable Scoring Inputs

Dependencies: current canonical builder, feature builder, quantile forecaster.

Scope:

- Add `is_censored_demand` to canonical daily rows when sales are constrained by zero or insufficient available stock.
- Add training controls for excluding or down-weighting censored rows.
- Persist store and product vocabularies with fitted model artifacts.
- Add unknown-category handling for cold-start scoring.

Acceptance gates:

- `tests/test_retail_adapter.py` includes a zero-sale, zero-stock case and asserts the row is marked censored.
- `tests/test_features.py` proves category encodings match between a full training frame and a filtered scoring frame.
- `tests/test_forecasting_horizon.py` proves serialized model artifacts preserve vocabularies.
- Demo output includes censored-row count in forecast metrics.

Metrics:

- Censored-row rate by store/product segment.
- Median pinball loss with and without censored-row handling.
- Scoring fallback rate for unknown products/stores.

Migration:

- Add a nullable `is_censored_demand` field to local and dbt canonical outputs.
- Include vocabularies in model serialization.

Rollback:

- Keep default demo behavior compatible by treating missing `is_censored_demand` as `False`.

## Milestone 2: Segment-Aware Forecast Calibration

Dependencies: Milestone 1 canonical fields and stable scoring metadata.

Scope:

- Extend forecast metrics by store, product class, promotion flag, shelf-life band, demand-volume band, and intermittent-demand flag.
- Add conformal calibration by segment with minimum sample thresholds and fallback to global adjustment.
- Add monitoring alerts that identify the failing segment and affected row count.

Acceptance gates:

- `tests/test_conformal.py` includes two noise segments and asserts segment-specific adjustments.
- `tests/test_monitoring.py` fails when any priority segment under-covers below the configured floor.
- `reports/example_run/forecast_metrics.json` includes global and segmented coverage summaries.

Metrics:

- Empirical coverage per configured segment.
- Mean interval width per segment.
- Undercoverage alert count and affected demand share.

Migration:

- Extend `ForecastConfig` and `MonitoringConfig` with segment fields and minimum segment size.
- Add metrics JSON schema version.

Rollback:

- Disable segmented adjustment while retaining global conformal calibration.

## Milestone 3: Operational Event-Order Validation

Dependencies: current simulator and policy interfaces.

Scope:

- Add named simulator event-order modes for expiry, receiving, shrinkage, sales, and order placement.
- Preserve the current mode as the default.
- Document when each mode matches store operations.
- Add stress fixtures for one-day and two-day shelf-life products.

Acceptance gates:

- `tests/test_inventory.py` includes one-day shelf-life fixtures that produce distinct expected waste/fill results under each supported mode.
- Simulator output includes the selected event-order mode in daily rows and summary metrics.
- `docs/MODELLING_DECISIONS.md` states the default event sequence and alternatives.

Metrics:

- Fill-rate delta by event-order mode.
- Waste-rate delta by event-order mode.
- Sensitivity for shelf-life bands.

Migration:

- Add `event_order_mode` to `InventoryConfig` with a default matching current behavior.

Rollback:

- Set `event_order_mode` to the current default.

## Milestone 4: Constrained Policy Promotion

Dependencies: Milestones 1 and 2 for segment attributes and reliable metrics.

Scope:

- Add policy selection logic that minimizes cost subject to global and segment fill-rate floors.
- Add explicit rejection reasons for policies that violate constraints.
- Add report sections for feasible frontier, rejected policies, and selected policy.

Acceptance gates:

- `tests/test_monitoring.py` or a new evaluation test proves a cheaper policy is rejected when it violates a service floor.
- `reports/example_results.md` names feasible policies and selected policy with constraint status.
- No existing policy metric columns are removed.

Metrics:

- Total cost among feasible policies.
- Global fill rate.
- Minimum segment fill rate.
- Waste rate and average inventory among feasible policies.

Migration:

- Extend policy metrics with `constraint_status`, `violated_constraints`, and `selected`.

Rollback:

- Continue publishing all policy metrics while disabling automatic promotion.

## Milestone 5: Warehouse And Orchestration Verification

Dependencies: stable local pipeline and metric schemas.

Scope:

- Add dbt parse/build validation with fixture data.
- Add Airflow DAG import validation.
- Add optional cloud integration tests gated by environment variables.
- Add a dry-run publication path for BigQuery partition overwrite.

Acceptance gates:

- CI runs Python checks plus dbt parse and DAG import checks.
- `tests/test_deployment.py` verifies publication order through a fake client, not only generated SQL.
- `gcp/DEPLOYMENT_RUNBOOK.md` includes exact rollback command sequence for a failed partition.

Metrics:

- CI duration and pass rate.
- dbt model test count.
- Cloud dry-run publication status.

Migration:

- Add dbt and Airflow validation dependencies to an optional dev group or CI-only install path.

Rollback:

- Keep cloud validation optional and leave local Python CI unchanged if cloud dependencies fail.

## Milestone 6: Public Dataset Benchmark

Dependencies: Milestones 1 through 5.

Scope:

- Add a real public retail dataset adapter with documented license and data-preparation assumptions.
- Produce a benchmark run artifact separate from synthetic demo artifacts.
- Compare baseline, calibrated, and constrained policies under the same evaluation split.

Acceptance gates:

- Adapter has fixture-backed contract tests.
- Benchmark command is documented and reproducible.
- Report distinguishes observed sales, estimated demand, stockout assumptions, and policy metrics.

Metrics:

- Pinball loss, coverage, CRPS.
- Fill-rate and waste proxy metrics available in the dataset.
- Runtime and memory footprint.

Migration:

- Add dataset-specific config without changing the synthetic demo defaults.

Rollback:

- Keep benchmark behind an explicit command/config path.
