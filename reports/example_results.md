# Example Results

This committed report is produced from a deterministic synthetic run:

```bash
poetry run perishable-lab demo --days 180 --stores 3 --products 8 --seed 42 --output-dir artifacts/example
```

The run contains **744 untouched test rows** after chronological training and calibration windows. It is evidence that the pipeline executes end to end; it is not evidence of commercial impact.

## Probabilistic forecast

| Metric | Value |
|---|---:|
| 80% interval empirical coverage | 0.809 |
| 90% interval empirical coverage | 0.929 |
| Approximate CRPS | 1.778 |
| Median pinball loss | 1.827 |
| Mean 90% interval width | 16.261 |

![Calibration](example_run/calibration.png)

The 90% interval slightly overcovers in this run. The appropriate next step is segmented calibration analysis, because good global coverage can conceal undercoverage for promotions, intermittent products, or individual stores.

## Inventory-policy comparison

| Policy | Fill rate | Waste rate | Cost per demand unit |
|---|---:|---:|---:|
| fixed service level | 0.892 | 0.064 | 0.381 |
| median baseline | 0.670 | 0.028 | 0.580 |
| economic newsvendor | 0.568 | 0.023 | 0.666 |

![Policy frontier](example_run/policy_frontier.png)

The fixed service-level policy is strongest under this synthetic cost configuration. The economic critical-fractile policy under-orders because the simple one-period cost approximation assigns a relatively low penalty to underage. That is a useful finding rather than a result to hide: policy quality depends on credible economics, service constraints, and a lead-time formulation, not merely on inserting a textbook newsvendor equation.

## Interpretation

- The forecast distribution is sufficiently calibrated to support a policy experiment at aggregate level.
- A median policy leaves substantial availability on the table.
- Raising the target quantile improves fill rate but increases waste and average inventory.
- The unconstrained economic policy can violate an operationally acceptable service floor. A production version should optimise cost subject to a minimum service constraint and should estimate costs with retailer stakeholders.
- Results should next be broken down by demand volume, shelf life, promotion status, store, and intermittent-demand class.
