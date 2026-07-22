# Public Retail Dataset Adapter and Benchmark

The public benchmark uses the M5 Forecasting Accuracy dataset as a user-provided input. The repository does not commit raw competition data. A clean user can obtain the data legally by accepting the Kaggle competition terms and placing the required CSV files under a local raw directory.

## Dataset Choice

| Candidate | Fit | Main gap | Decision |
| --- | --- | --- | --- |
| M5 Forecasting Accuracy | Daily item-store unit sales, prices, calendar events, and hierarchy. | No stock, waste, expiry, supplier lead time, or stockout labels. | Selected. |
| Corporacion Favorita Grocery Sales Forecasting | Grocery domain, item and store metadata, promotions, holidays, transactions, and oil. | Large files and no direct stock or waste fields. | Not selected for the first adapter. |
| Rossmann Store Sales | Store-level sales, promotions, holidays, and store metadata. | No item grain and no perishable inventory fields. | Not selected. |

Source and access:

- M5: <https://www.kaggle.com/competitions/m5-forecasting-accuracy>
- Favorita: <https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting>
- Rossmann: <https://www.kaggle.com/competitions/rossmann-store-sales>

## Required Files

Place these files in the raw directory:

- `calendar.csv`
- `sales_train_validation.csv`
- `sell_prices.csv`

Optional checksum validation is supported through `M5AdapterConfig.expected_checksums`.

## Leakage Notes

The adapter flags obvious competition leakage sources:

- `sales_train_evaluation.csv`
- `sample_submission.csv`
- day columns beyond the validation training window

The benchmark uses `sales_train_validation.csv` and creates time-based rolling windows from historical day columns only.

## Canonical Conversion

`load_m5_canonical` converts the wide M5 sales matrix into one row per date, store, and product. It joins calendar and weekly price fields and preserves source identifiers.

Observed public fields:

- `date`
- `store_id`
- `product_id`
- `demand`
- `price`
- `promotion`
- hierarchy fields from M5

Synthetic supplements:

- `shelf_life_days`
- `lead_time_days`
- `unit_cost`
- `unit_margin`
- `waste_cost`
- `shrinkage_rate`
- `record_error_std`

These supplements exist only so repository interfaces that expect perishable-inventory fields can run. Forecast metrics on observed sales are the valid public-data conclusion. Inventory, waste, and lead-time conclusions remain synthetic unless real operational data is added.

## Benchmark

Run:

```bash
poetry run perishable-lab public-retail-benchmark data/raw/m5 --output-dir artifacts/public-retail-benchmark
```

The benchmark writes:

- `canonical_sample.csv`
- `date_completeness.csv`
- `forecast_metrics.csv`
- `benchmark_manifest.json`
- `synthetic_comparison.md`

Models:

- seasonal empirical quantiles
- SBA intermittent-demand point baseline with conservative interval spread
- quantile gradient boosting with split-conformal interval adjustment

Evaluation:

- rolling-origin windows
- pinball loss by quantile
- empirical interval coverage
- mean interval width
- approximate CRPS

## Limitations

M5 is useful for testing demand-forecasting interfaces on real retail sales. It does not prove the inventory simulator is calibrated to store operations. The adapter deliberately labels all inventory, shelf-life, waste, shrinkage, cost, and lead-time fields as synthetic supplements.
