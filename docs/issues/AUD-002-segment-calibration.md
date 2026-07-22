# High: Add Segment-Aware Calibration

## Problem

Global interval coverage can pass while priority store, product, promotion, or shelf-life segments under-cover.

## Evidence

- `src/perishable_lab/forecasting/conformal.py`
- `src/perishable_lab/forecasting/metrics.py`
- `src/perishable_lab/monitoring/quality.py`
- `tests/test_conformal.py`
- `tests/test_monitoring.py`

## Required Work

- Compute coverage by configured segment.
- Support segment-level conformal adjustments with minimum sample thresholds.
- Fall back to global calibration when a segment is too small.
- Emit monitoring alerts with segment identifier and affected row count.

## Acceptance Criteria

- Tests include two demand segments with different error distributions.
- Monitoring fails when any priority segment falls below the configured floor.
- Example metrics include global and segmented coverage summaries.
