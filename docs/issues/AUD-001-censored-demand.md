# Blocker: Add Censored-Demand Handling

## Problem

Observed sales can be recorded as ordinary demand even when inventory availability constrained customer purchases.

## Evidence

- `src/perishable_lab/data/canonical.py`
- `src/perishable_lab/features.py`
- `docs/READINESS_REVIEW.md`

## Required Work

- Add `is_censored_demand` to canonical daily rows.
- Mark rows censored when observed availability implies demand may have exceeded sales.
- Add training controls for exclusion, weighting, or adjustment.
- Report censored-row rate in forecast metrics.

## Acceptance Criteria

- A zero-sale, zero-stock fixture is marked censored.
- Forecast training can exclude or adjust censored rows.
- Existing demo defaults continue to run when the field is missing.
