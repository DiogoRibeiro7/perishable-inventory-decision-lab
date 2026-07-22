# Experiment Plan

## Primary hypothesis

A calibrated distributional forecast connected to an economic ordering policy reduces total operating cost relative to a median-demand baseline while preserving an agreed availability floor.

## Experimental units

- Primary: store-product-day.
- Aggregation: product, store, department proxy, and total network.
- Time split: expanding or rolling origin, never random rows.

## Baselines

1. Last-7-day mean demand.
2. Seasonal naive demand from seven days earlier.
3. Median quantile model with order-up-to policy.
4. Fixed service-level quantile policy.
5. Economic critical-fractile policy.
6. Clairvoyant lower bound for regret analysis, clearly labelled non-deployable.

## Forecast metrics

- Pinball loss at all trained quantiles.
- Approximate CRPS.
- Empirical coverage and interval width.
- Coverage by demand volume, shelf life, store, product, promotion, and intermittency.
- Quantile crossing before correction.

## Operational metrics

- Fill rate and days with any stockout.
- Waste and expiry rate.
- Lost margin, disposal cost, holding cost, and total cost.
- Average inventory and order volatility.
- Policy regret relative to the lower bound.
- Robustness under inventory-record error and demand shocks.

## Stress tests

- Promotion uplift outside the training range.
- Supplier lead time changes from one to two days.
- Shelf life reduced by one day.
- Shrinkage doubled.
- Missing stock snapshots.
- Demand level shift and sudden store closure.
- Cold-start product with a mapped product family but little history.

## Promotion criteria

A candidate policy is promoted only when it:

- Meets the minimum fill-rate constraint.
- Improves total cost over the incumbent across several temporal folds.
- Does not create unacceptable regressions for high-priority products or stores.
- Remains stable under stress tests.
- Produces explanations and fallback behaviour understood by operations teams.

## Reporting

Each demo run writes an evaluation report that keeps forecast metrics, policy rankings, and monitoring status separate. Paired temporal resampling utilities are available for candidate-versus-baseline cost comparisons when fold-level or day-level paired results are collected.
