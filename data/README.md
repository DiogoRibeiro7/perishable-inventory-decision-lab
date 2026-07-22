# Data

The executable demo generates its own data and writes it under `artifacts/`. No generated data is committed.

A production adapter should map source systems into the following daily contract:

- `date`
- `store_id`
- `product_id`
- `demand`
- `price`
- `promotion`
- `shelf_life_days`
- `lead_time_days`
- `unit_cost`
- `unit_margin`
- `waste_cost`
- `shrinkage_rate`
- `record_error_std`

Recommended additional fields include sales, censored-demand indicators, stock snapshots, waste reason, supplier/product mapping, category hierarchy, order cut-off, case pack, delivery calendar, display minimum, markdown, weather, holidays, and local events.
