# Readiness Review

This review looks for real-world failure modes before shadow deployment.

## Findings

### High: Sales are still treated as demand under stockouts

- File and line: `src/perishable_lab/data/canonical.py:126`
- Failure scenario: a store sells zero units because the shelf is empty, and the canonical builder records zero demand. The forecaster learns that demand disappeared rather than that sales were censored by unavailable inventory.
- Why current tests do not catch it: tests verify duplicate handling and product mapping, but they do not assert a separate censored-demand treatment or correction path.
- Minimal reproducible test: build a daily row with `quantity = 0` and a stock snapshot with `on_hand_quantity = 0`; assert the canonical output marks the row as censored and downstream training can exclude or adjust it.
- Recommended fix: add an explicit censored target flag to feature construction and train/evaluate with either exclusion, imputation, or a censored-demand estimator.
- Interface impact: adds a public column to the canonical data contract.

### High: Conformal calibration is only marginal

- File and line: `src/perishable_lab/forecasting/conformal.py:35`
- Failure scenario: global interval coverage is acceptable while high-volume promoted products are undercovered, causing systematic under-ordering in the costly tail.
- Why current tests do not catch it: tests only verify that intervals expand globally.
- Minimal reproducible test: create two demand segments with different noise levels and assert segmented coverage is reported separately.
- Recommended fix: add segmented calibration diagnostics with minimum sample thresholds and shrinkage toward the global adjustment.
- Interface impact: extends forecast metrics and monitoring reports.

### Medium: Product encoding can shift between training and scoring batches

- File and line: `src/perishable_lab/features.py:52`
- Failure scenario: categorical codes are recomputed from each input frame, so a product can receive a different numeric code when scoring a subset or a later batch.
- Why current tests do not catch it: feature tests build a single frame and do not compare train-time versus score-time encoding.
- Minimal reproducible test: build features for a full frame and for a filtered scoring frame; assert product/store encodings are stable.
- Recommended fix: persist store and product vocabularies with the model and use an unknown category code for cold starts.
- Interface impact: changes model artifacts and scoring metadata.

### Medium: Expiry sequence is fixed and may not match store operations

- File and line: `src/perishable_lab/inventory/simulator.py:226`
- Failure scenario: units expire before same-day delivery and sales are processed, but some retailers remove expiry at close or before opening. Waste and fill rate can change materially for short shelf-life items.
- Why current tests do not catch it: conservation tests assert non-negative stock and demand accounting, not operational event-order sensitivity.
- Minimal reproducible test: compare a one-day shelf-life item under open-time versus close-time expiry and assert the chosen sequence is explicit.
- Recommended fix: add an event-order configuration with documented defaults and fixtures for supported sequences.
- Interface impact: extends simulator configuration.

### Medium: Policy selection optimises aggregate cost only

- File and line: `src/perishable_lab/evaluation/reporting.py:62`
- Failure scenario: the selected policy lowers total cost but harms service for a critical product segment or store cluster.
- Why current tests do not catch it: tests check report creation, not constrained selection by segment-level service floors.
- Minimal reproducible test: create policy metrics where the lowest-cost policy violates a fill-rate floor and assert it is not selected.
- Recommended fix: add constrained selection criteria and segmented policy ranking.
- Interface impact: changes evaluation report semantics.

### Low: Demo does not exercise cloud publication paths

- File and line: `gcp/DEPLOYMENT_RUNBOOK.md:4`
- Failure scenario: local tests pass while a partition overwrite, service account, or Cloud Run override fails during deployment.
- Why current tests do not catch it: deployment helper tests validate generated strings and payloads only.
- Minimal reproducible test: add a dry-run integration job against a sandbox project or a mocked BigQuery client that verifies delete-and-insert SQL execution order.
- Recommended fix: add an optional integration test suite gated by environment variables.
- Interface impact: no public runtime interface change.

## Recommendation

No-go for live recommendation publication. The project is suitable for local demonstration and shadow-style evaluation, but the stockout-censoring, segmented calibration, stable categorical encoding, event-order validation, and constrained policy selection gaps should be closed before operational use.

## Experiments Required Before Reconsideration

1. Stockout-censoring experiment comparing naive sales targets with censored-demand correction.
2. Segmented calibration experiment by demand volume, promotion, shelf life, store, and product.
3. Encoding-stability test across train, calibration, and scoring slices with cold-start products.
4. Event-order sensitivity analysis for short shelf-life products.
5. Policy promotion test that enforces minimum fill rate globally and by priority segment.
