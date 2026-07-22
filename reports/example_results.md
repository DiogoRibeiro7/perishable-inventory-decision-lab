# Example Results

This committed report is produced from a deterministic synthetic run:

```bash
poetry run perishable-lab demo --days 90 --stores 2 --products 4 --seed 42 --output-dir reports/example_run
```

The run contains **104 untouched test rows** after chronological training and calibration windows. It is evidence that the pipeline executes end to end; it is not evidence of commercial impact.

## Probabilistic forecast

| Metric | Value |
|---|---:|
| 90% interval empirical coverage | 0.894 |
| Approximate CRPS | 1.538 |
| Median pinball loss | 1.593 |
| Mean 90% interval width | 11.549 |
| Censored rows in default synthetic run | 0 |

![Calibration](example_run/calibration.png)

The 90% interval is close to nominal in this run. The appropriate next step is segmented calibration analysis, because good global coverage can conceal undercoverage for promotions, intermittent products, or individual stores.

## Inventory-policy comparison

| Policy | Fill rate | Waste rate | Cost per demand unit |
|---|---:|---:|---:|
| fixed service level | 0.820 | 0.044 | 0.360 |
| median baseline | 0.632 | 0.022 | 0.428 |
| economic newsvendor | 0.296 | 0.010 | 0.568 |

![Policy frontier](example_run/policy_frontier.png)

The fixed service-level policy is strongest under this synthetic cost configuration. The economic critical-fractile policy under-orders because the simple one-period cost approximation assigns a relatively low penalty to underage. That is a useful finding rather than a result to hide: policy quality depends on credible economics, service constraints, and a lead-time formulation, not merely on inserting a textbook newsvendor equation.

## Interpretation

- The forecast distribution is sufficiently calibrated to support a policy experiment at aggregate level.
- A median policy leaves substantial availability on the table.
- Raising the target quantile improves fill rate but increases waste and average inventory.
- The unconstrained economic policy can violate an operationally acceptable service floor. A production version should optimise cost subject to a minimum service constraint and should estimate costs with retailer stakeholders.
- Censoring diagnostics are now reported by store, product, demand-volume band, and shelf-life band.
