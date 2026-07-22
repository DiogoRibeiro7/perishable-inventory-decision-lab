# Interview Walkthrough

## Reproducible Command

```bash
poetry install
poetry run perishable-lab demo --days 180 --stores 3 --products 8 --seed 42 --output-dir artifacts/example
```

The example run finishes on a laptop-scale dataset and writes forecast metrics, policy metrics, monitoring status, an evaluation report, row-level forecasts, and row-level inventory simulations.

## Ten-Minute Narrative

### Minute 1: Operational framing

Fresh-food replenishment is not only a forecast problem. An order can be wrong because demand was uncertain, stock records were wrong, units expired, lead time shifted, or the chosen service target was misaligned with business costs. The project therefore evaluates the decision: waste, lost sales, fill rate, inventory, and total cost.

### Minutes 2-6: System walkthrough

1. The data layer validates one row per store-product-day and rejects duplicate keys, negative demand, invalid shelf life, invalid lead time, and missing critical values.
2. Feature engineering uses shifted lags and rolling windows, so the target day does not leak into the predictors.
3. The forecasting layer estimates demand quantiles, projects crossing quantiles back into monotone order, and calibrates the central interval on a later time window.
4. The simulator keeps FIFO shelf-life cohorts, pending deliveries, inventory-record noise, shrinkage, expiry, and lost sales separate.
5. The policy layer compares a median baseline, a fixed service-level order-up-to rule, an economic critical-fractile rule, and newer constrained/age-aware policy components.
6. The evaluation layer reports forecast quality, operational quality, monitoring alerts, and policy rankings separately.

### Minutes 7-8: Results discussion

| Policy | Fill rate | Waste rate | Cost per demand unit |
|---|---:|---:|---:|
| fixed service level | 0.892 | 0.064 | 0.381 |
| median baseline | 0.670 | 0.028 | 0.580 |
| economic newsvendor | 0.568 | 0.023 | 0.666 |

The fixed service-level policy is strongest in the committed synthetic run because it improves availability enough to offset higher inventory and waste. The unconstrained economic rule under-orders under the configured cost assumptions, which is a useful diagnostic: credible operations economics matter as much as the forecasting model.

The calibration graphic is in [`reports/example_run/calibration.png`](../reports/example_run/calibration.png), and the waste-versus-fill-rate frontier is in [`reports/example_run/policy_frontier.png`](../reports/example_run/policy_frontier.png).

### Minutes 9-10: Limitations and next steps

Synthetic data validates engineering structure and reasoning, not commercial lift. With real retailer data, the next priorities are stockout-censoring correction, segmented calibration, stable product/store encodings, event-order validation, and policy selection with hard service constraints.

## Three Difficult Examples

1. **High promotion, low observed sales.** The model may treat low sales as low demand, but the true reason could be a stockout during promotion. The canonical layer now carries stockout visibility, but the forecast target still needs censored-demand correction.
2. **Short shelf life with late supplier delivery.** A service-level policy can order correctly on paper and still create waste if the delivery arrives after the sellable window. The simulator now records effective lead time and supplier fill quantity for stress tests.
3. **Cold-start product remap.** A supplier item ID can change while the stable demand entity remains the same. The source builder uses effective-dated product mapping; forecasting still needs persisted categorical vocabularies before production scoring.

## Role Mapping

| Capability | Repository evidence |
|---|---|
| Probabilistic forecasting | Quantile models, conformal calibration, lead-time utilities, empirical fallback. |
| Decision science | Forecast distributions drive replenishment policies evaluated on waste, availability, lost sales, and cost. |
| Operations research | Critical-fractile policy, base-stock rules, hard constraints, capacity and case-pack handling. |
| Data engineering | Typed source contracts, local/cloud adapters, dbt staging and mart examples. |
| MLOps | Docker, CI, run metadata, model versioning fields, deployment runbook, idempotent publication helpers. |
| Communication | Architecture, modelling decisions, experiment plan, readiness review, and this walkthrough. |

## Likely Technical Questions

1. **Why not use a point forecast?** Ordering needs tail probabilities because stockout and waste costs are asymmetric.
2. **Why quantile gradient boosting?** It is a strong tabular baseline for heterogeneous retail panels and gives policy-ready distribution points.
3. **How do you prevent leakage?** Demand lags and rolling statistics are shifted; splits are chronological.
4. **What does conformal calibration add?** It adjusts interval coverage using held-out calibration residuals.
5. **Where can conformal calibration fail?** Marginal coverage can hide segment undercoverage under promotions, intermittency, or store-level shifts.
6. **How are stockouts handled?** They are surfaced as a data-contract concern; the current forecast still needs explicit censored-demand correction.
7. **What is the main simulator assumption?** FIFO age cohorts approximate sell-through and expiry; event ordering must match the retailer process.
8. **Why compare policy metrics separately from forecast metrics?** A statistically better forecast can produce worse decisions if errors occur in expensive tails.
9. **Why did the economic policy underperform?** The configured underage cost was too low relative to the service implications.
10. **How would you choose a policy in production?** Minimise cost subject to global and segment-level service floors.
11. **How do you handle product ID changes?** Effective-dated mappings preserve stable demand entities.
12. **How do you handle cold starts?** Use hierarchy-backed empirical fallbacks first; later persist learned encodings and category-level priors.
13. **What would you monitor after launch?** Freshness, duplicate keys, missingness, coverage, pinball loss, fill rate, overrides, waste, and fallback rate.
14. **How would you test business impact?** Start in shadow mode, then run a controlled store/product experiment with guardrails.
15. **How is reproducibility handled?** Deterministic seeds, config hashes, model/policy versions, generated timestamps, and run manifests.
16. **What makes a batch idempotent?** Deterministic execution IDs and partition-scoped delete-and-insert publication.
17. **What is the biggest real-data risk?** Observed sales are not latent demand when shelves are empty.
18. **What is the biggest modelling risk?** Aggregate calibration can hide costly tail failures in important segments.
19. **What is the biggest operations risk?** Recommendations may ignore constraints or staff workflows not represented in the data.
20. **What would you build next?** Censored-demand correction, segmented calibration, stable encodings, event-order fixtures, and constrained policy promotion.
