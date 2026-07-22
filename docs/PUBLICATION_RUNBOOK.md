# Recommendation Publication

The service boundary is batch-first. Store systems consume only complete, immutable recommendation batches through a read-only file contract. An HTTP service is not required until there is a real interactive workflow.

## Job Boundary

Each step is a separate command or Cloud Run Job:

- `train`
- `calibrate`
- `score`
- `simulate`
- `recommend`
- `validate`
- `stage`
- `publish`
- `rollback`

Job ids are deterministic over retailer, business date, configuration hash, data version, model version, and policy version. A retry with the same inputs resolves to the same batch id.

## Schemas

Request schema `recommendation_request.v1`:

- `retailer_id`
- `business_date`
- `config_hash`
- `data_version`
- `model_version`
- `policy_version`

Output schema `recommendation_output.v1`:

- `business_date`
- `store_id`
- `product_id`
- `recommended_order_quantity`
- `unit`
- `model_version`
- `policy_version`
- `generated_at`
- `input_feature_set_hash`

The store-facing contract exposes `active_order_quantity`, the original policy version, feature-set hash, and any override reason. Store readers never read the staging location.

## Publication State

```text
validated batch
  -> staged immutable artifact
  -> atomic active pointer swap
  -> active read-only contract
  -> rollback pointer swap to previous valid batch
```

Publication validates completeness before staging. The active pointer is replaced atomically only after the artifact hash and row count match the manifest. A partially scored batch cannot become active because staging rejects failed validation and readers only follow the active pointer.

## Validation

Blocking checks include:

- Missing required columns.
- Duplicate store-product-date rows.
- Missing expected rows.
- Stale generated timestamps.
- Model or policy version mismatch.
- Incompatible units.
- Negative or non-whole quantities.
- Implausible jumps from the previous active batch.
- Artifact hash mismatch.
- Active pointer generation conflict.

## Implementations

Local filesystem:

- Batch artifacts live under `batches/<batch_id>/`.
- `manifest.json` stores row count, request schema, output schema, and artifact hash.
- `active.json` stores the current batch id, previous batch id, and generation.

Warehouse:

- Stage complete batches in BigQuery and Cloud Storage.
- Publish with a transaction that archives the prior active rows and inserts the staged batch.
- Require an expected active generation to block concurrent publish conflicts.
- Run Cloud Run Jobs for batch work.

## Commands

```bash
poetry run perishable-lab publish-recommendations recommendations.csv --business-date 2026-01-05 --expected-rows 120 --expected-unit unit
poetry run perishable-lab rollback-recommendations
```

## Overrides And Fallback

Human overrides record user, reason, business date, store, product, and override quantity while preserving the original recommendation. If validation or publish fails, the previous valid batch remains active. Rollback swaps the active pointer back to that previous valid batch and keeps the failed artifact out of the store-facing contract.
