# High: Persist Stable Scoring Encodings

## Problem

Store and product category codes are recomputed from each feature frame, which can change model inputs between training and scoring.

## Evidence

- `src/perishable_lab/features.py`
- `src/perishable_lab/forecasting/quantile.py`
- `tests/test_features.py`
- `tests/test_forecasting_horizon.py`

## Required Work

- Persist store and product vocabularies with fitted model artifacts.
- Use persisted mappings during scoring.
- Add a stable unknown-category value for cold-start stores and products.

## Acceptance Criteria

- A filtered scoring frame maps known stores and products to the same codes as the training frame.
- Unknown stores/products use a deterministic fallback code.
- Serialized model artifacts round-trip with vocabularies intact.
