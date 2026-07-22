# Release Notes

## v0.2.0

Demand contracts now distinguish observed sales from demand signals that may be censored by availability.

### Added

- Canonical daily rows include `is_censored_demand`, `censoring_reason`, `observed_inventory`, `late_stock_snapshot`, `stockout_flag`, latent-demand estimates, bounds, provenance, and training weights.
- Forecast training accepts row weights so censored rows can be included, excluded, or down-weighted by configuration.
- Demo forecast metrics include censored-row diagnostics and segment summaries by store, product, demand-volume band, and shelf-life band.

### Changed

- The demo target is the configured latent-demand estimate instead of raw observed sales.
- Feature selection keeps censoring/provenance columns in the modelling frame for audit while excluding them from model inputs.
- Release evidence now includes the root roadmap and a `v0.2.0` gate report.

### Migration

Existing input frames without the new censoring columns continue to be treated as uncensored. Source adapters that provide stock snapshots can now populate availability-aware canonical fields.

### Known limitations

The censored-demand path is deterministic and conservative. It surfaces and controls stockout-biased rows, but retailer-specific lost-sales behavior still requires operational validation.

## v0.1.0

Initial reproducible release of the perishable inventory decision lab.

### Included

- Deterministic synthetic demand generator and canonical daily demand contract.
- Leakage-controlled feature creation for lag, rolling, price, promotion, calendar, and inventory context.
- Quantile forecasting with calibration metrics and example plots.
- FIFO perishable inventory simulator with shelf life, lead time, shrinkage, record noise, supplier fill rate, capacity, case packs, and order constraints.
- Policy comparison across median, service-level, and economic newsvendor baselines.
- Monitoring reports, run manifests, and publication validation.
- Optional public retail benchmark adapter for user-provided M5 files.
- dbt, Airflow, Docker, CI, and GCP deployment examples.

### Evidence

- Example results: [`reports/example_results.md`](../reports/example_results.md)
- Architecture: [`docs/ARCHITECTURE_ONE_PAGER.md`](ARCHITECTURE_ONE_PAGER.md)
- Live demo guide: [`docs/LIVE_DEMO_GUIDE.md`](LIVE_DEMO_GUIDE.md)
- Final audit: [`docs/FINAL_RELEASE_AUDIT.md`](FINAL_RELEASE_AUDIT.md)

### Known limitations

The committed data is synthetic. It supports reproducibility and stress testing, not direct retailer outcome claims. A production rollout needs real source mappings, segment-level calibration, cost sign-off, and operational acceptance testing.
