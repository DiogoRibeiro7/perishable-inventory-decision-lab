# Feature Store Lineage

This design makes every prediction traceable to the exact values, source records, transformation versions, and availability timestamps used at the order cutoff.

## Time Semantics

| Field | Meaning |
| --- | --- |
| `event_time` | When the source event happened. |
| `effective_time` | When the source value becomes true for the store, product, or business entity. |
| `ingestion_time` | When the record first arrived in the platform. |
| `processing_time` | When feature transformation ran. |
| `business_date` | Store operating date used for planning and reporting. |

The point-in-time join includes a source row only when `effective_time <= order_cutoff` and `available_at <= order_cutoff`. Equality is allowed because the value is observable at the cutoff instant. Late arrivals and restatements keep their original effective time but receive a later availability time and version, so frozen runs do not change.

## Registry

Each feature registry entry records:

- Owner.
- Source table.
- Transformation.
- Unit.
- Availability delay.
- Freshness SLA.
- Null policy.
- Version.
- Data type.

Duplicate `(feature_name, version)` entries are invalid. Registry snapshots are hashed and stored with every feature-set manifest.

## Local And Warehouse Parity

Python feature generation and dbt outputs are compared on the same fixture keys with numeric tolerance. Required fixtures include cutoff equality, late stock counts, revised promotions, delayed counts, daylight-saving boundaries, product remapping, and duplicate-version rejection.

The dbt mart `fct_feature_set_daily` is partitioned by `business_date` and clustered by `store_id`, `product_id`, and `feature_set_version`. The local `point_in_time_join` function applies the same effective-time and availability-time filters.

## Frozen Snapshots

Training dataset snapshots persist:

- Feature value hash.
- Registry hash.
- Source partition manifest with row counts and partition hashes.
- Combined feature-set hash.

Use:

```bash
poetry run perishable-lab snapshot-features training_features.csv --output-path artifacts/feature-store/training_snapshot_manifest.json --partition-columns date
```

Rebuilding a frozen run is valid only when the combined hash and all source partition hashes match.

## Lineage Diagram

```text
raw source partitions
  -> staging contracts
  -> point-in-time transformations
  -> fct_feature_set_daily
  -> frozen training snapshot
  -> scoring batch inputs
  -> recommendation decision log
```

Every decision log should include the `feature_set_hash`, `feature_set_version`, feature availability timestamp, source partition manifest hash, and transformation version.
