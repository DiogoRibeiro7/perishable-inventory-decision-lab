# Repository Audit Report

Date: 2026-07-22

## Scope

This audit reviewed the Python package, tests, configuration, documentation, CI workflow, Dockerfile, dbt project, Airflow DAG, GCP examples, committed report artifacts, and the local numbered instruction set.

## Executive Assessment

The repository is a coherent local production prototype for probabilistic forecasting and perishable inventory decision evaluation. The core package is implemented and tested around synthetic data, canonical retail inputs, feature engineering, quantile forecasting, conformal calibration, FIFO perishable simulation, policy comparison, monitoring, reporting, and GCP helper utilities.

The cloud, dbt, Airflow, and portfolio materials are credible scaffolds rather than a runnable production deployment. The main technical risks are not model novelty; they are temporal correctness under real retail data, censored sales during stockouts, stable product/store identity at scoring time, segmented calibration, event-order validation, and constrained policy promotion.

## What Is Real

| Area | Status | Evidence |
|---|---|---|
| Typed Python package | Implemented | `src/perishable_lab`, `pyproject.toml`, `tests/` |
| Synthetic data demo | Implemented | `src/perishable_lab/data/synthetic.py`, `src/perishable_lab/pipelines/demo.py`, `tests/test_pipeline.py` |
| Canonical retail source contracts | Partially implemented | `src/perishable_lab/data/contracts.py`, `src/perishable_lab/data/canonical.py`, `tests/test_retail_adapter.py` |
| Leakage-safe feature construction | Implemented for local batch mode | `src/perishable_lab/features.py`, `tests/test_features.py` |
| Quantile forecasting | Implemented baseline | `src/perishable_lab/forecasting/quantile.py`, `tests/test_forecasting_horizon.py` |
| Conformal interval calibration | Implemented globally | `src/perishable_lab/forecasting/conformal.py`, `tests/test_conformal.py` |
| Lead-time forecast utilities | Partially implemented | `src/perishable_lab/forecasting/horizon.py`, `tests/test_forecasting_horizon.py` |
| FIFO perishable simulator | Implemented local simulator | `src/perishable_lab/inventory/simulator.py`, `tests/test_inventory.py` |
| Ordering policies | Implemented baseline and constrained rules | `src/perishable_lab/inventory/policies.py`, `tests/test_inventory.py` |
| Evaluation and reports | Implemented local reporting | `src/perishable_lab/evaluation/reporting.py`, `reports/example_results.md`, `reports/example_run/` |
| Monitoring checks | Implemented basic checks | `src/perishable_lab/monitoring/quality.py`, `tests/test_monitoring.py` |
| Reproducibility metadata | Implemented for demo outputs | `src/perishable_lab/pipelines/demo.py`, `tests/test_pipeline.py` |
| CI and container build | Implemented | `.github/workflows/ci.yml`, `Dockerfile` |
| GCP publication helpers | Implemented utility level | `src/perishable_lab/deployment/gcp.py`, `tests/test_deployment.py` |

## What Is Illustrative

| Area | Evidence | Why It Is Illustrative |
|---|---|---|
| dbt project | `dbt_project/models/` | Models and tests show the intended BigQuery shape, but there is no committed dbt execution artifact or fixture-backed dbt test run. |
| Airflow DAG | `airflow/dags/perishable_decision_pipeline.py` | DAG expresses orchestration intent, but provider dependencies and cloud resources are not validated in CI. |
| Cloud Build deployment | `gcp/cloudbuild.yaml` | Build and deploy commands are present, but no environment-specific Terraform, IAM policy, or successful deployment proof is committed. |
| Public benchmark adapter | `src/perishable_lab/data/adapters.py` | Local and BigQuery adapters exist, but no real public retail dataset adapter or benchmark result is committed. |
| Portfolio walkthroughs | `docs/INTERVIEW_WALKTHROUGH.md`, `docs/CASE_STUDY.md` | Accurate as narrative material, but they should continue to distinguish local evidence from production claims. |

## Unsupported Or Absent

| Capability | Status | Gap |
|---|---|---|
| Stockout-censored demand training target | Absent | Sales can still be interpreted as demand when stock is unavailable. |
| Segment-level calibration and monitoring | Partially implemented | Global interval coverage is measured; store/product/promotion/shelf-life coverage is not enforced. |
| Stable categorical encodings for scoring | Absent | `build_features` recomputes category codes per frame, which can shift train versus score mappings. |
| Operational event-order configuration | Absent | Simulator event order is fixed rather than retailer-configurable and validated. |
| Policy selection with service constraints | Partially implemented | Metrics are reported, but promotion criteria do not enforce global and segment-level service floors. |
| End-to-end cloud integration test | Absent | Local helper tests validate payloads and SQL strings only. |
| Feature store lineage and point-in-time joins | Scaffold only | dbt sources and canonical builder support cutoffs, but no feature store contract or lineage manifest exists. |
| Live recommendation API | Absent | Batch-oriented demo and Cloud Run job pattern exist; no service endpoint is implemented. |

## Findings

### Blocker: Sales Are Still Used As Demand Under Stockout Conditions

- Evidence: `src/perishable_lab/data/canonical.py`, `src/perishable_lab/features.py`, `docs/READINESS_REVIEW.md`
- Severity: Blocker for live use
- Failure mode: zero or low observed sales during an empty-shelf period trains the model to expect lower demand instead of recognizing censored demand.
- Current coverage: `tests/test_retail_adapter.py` checks source deduplication, mapping, cutoff behavior, and fail-closed validation, but does not assert censored target behavior.
- Acceptance gate: canonical output includes `is_censored_demand`; training can exclude, weight, or adjust censored rows; a test proves a zero-sale empty-stock row is not treated as ordinary zero demand.

### High: Calibration Is Global Rather Than Segment-Aware

- Evidence: `src/perishable_lab/forecasting/conformal.py`, `src/perishable_lab/forecasting/metrics.py`, `src/perishable_lab/monitoring/quality.py`, `tests/test_conformal.py`, `tests/test_monitoring.py`
- Severity: High
- Failure mode: aggregate coverage can pass while promoted items, short-life products, or high-volume stores under-cover and create avoidable stockouts.
- Current coverage: tests verify interval expansion and global alert generation only.
- Acceptance gate: metrics and monitoring report coverage by segment with minimum sample thresholds and fail when any priority segment falls below the configured floor.

### High: Product And Store Encodings Can Drift Between Training And Scoring

- Evidence: `src/perishable_lab/features.py`, `src/perishable_lab/forecasting/quantile.py`, `tests/test_features.py`, `tests/test_forecasting_horizon.py`
- Severity: High
- Failure mode: category codes are recomputed from each frame, so a product/store can map to a different numeric value in a later scoring batch.
- Current coverage: tests validate a single feature frame, not train/score parity.
- Acceptance gate: fitted vocabularies are serialized with the model; scoring uses the same mappings plus an unknown category; a regression test compares full-frame and filtered-frame scoring.

### High: Simulator Event Order Is Fixed But Business-Critical

- Evidence: `src/perishable_lab/inventory/simulator.py`, `tests/test_inventory.py`, `docs/MODELLING_DECISIONS.md`
- Severity: High
- Failure mode: expiry, delivery receipt, shrinkage, sales, and order placement sequence materially changes waste and fill rate for short shelf-life items.
- Current coverage: conservation and non-negative assertions pass, but event-order alternatives are not tested.
- Acceptance gate: simulator exposes named event-order modes; fixtures demonstrate one-day shelf-life behavior under supported modes; docs state the default operational assumption.

### High: Policy Promotion Does Not Enforce Service Floors

- Evidence: `src/perishable_lab/evaluation/reporting.py`, `reports/example_results.md`, `tests/test_monitoring.py`
- Severity: High
- Failure mode: the lowest-cost policy can be selected even if a priority segment violates availability requirements.
- Current coverage: policy metrics are generated and reported, but no constrained selection test exists.
- Acceptance gate: policy ranking supports cost minimization subject to global and segment fill-rate floors; a test proves a lower-cost policy is rejected when it violates the floor.

### Medium: Cloud Workflow Is Not Verified End To End

- Evidence: `gcp/cloudbuild.yaml`, `gcp/DEPLOYMENT_RUNBOOK.md`, `airflow/dags/perishable_decision_pipeline.py`, `src/perishable_lab/deployment/gcp.py`, `tests/test_deployment.py`
- Severity: Medium
- Failure mode: payload and SQL helpers pass locally while IAM, job execution, partition publication, or Airflow provider configuration fails in a real project.
- Current coverage: deterministic execution IDs, Cloud Run overrides, and BigQuery SQL generation are unit-tested.
- Acceptance gate: optional integration tests run against a sandbox project or mocked cloud clients with execution-order assertions.

### Medium: dbt Models Lack Fixture-Backed Validation In CI

- Evidence: `dbt_project/models/`, `dbt_project/packages.yml`, `.github/workflows/ci.yml`
- Severity: Medium
- Failure mode: SQL shape or dbt package changes can break the warehouse layer without failing CI.
- Current coverage: GitHub Actions runs Python linting, typing, tests, and Docker build; dbt is not executed.
- Acceptance gate: CI runs `dbt parse` plus fixture-backed `dbt build` or equivalent SQL compilation checks.

## Reproducibility And Delivery Controls

- Dependency pinning is handled through `poetry.lock`; Python support is `>=3.11,<3.13`.
- CI runs Python 3.11 and 3.12 for linting, typing, and tests.
- The demo uses deterministic synthetic generation and includes run metadata with config hash, generation timestamp, model version, and policy version.
- Report artifacts in `reports/example_run/` provide concrete output evidence.
- Runtime artifacts should continue to be written outside tracked source paths unless they are curated examples.

## Production Readiness Decision

Status: no-go for live replenishment publication; suitable for portfolio demonstration, local end-to-end validation, and shadow evaluation planning.

The next delivery milestone should address censored demand, stable scoring encodings, segmented calibration, and constrained policy selection before adding more advanced models.
