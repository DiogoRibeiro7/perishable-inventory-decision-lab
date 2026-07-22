# Release Notes

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
