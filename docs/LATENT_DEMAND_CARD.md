# Latent Demand Card

## Meaning

Latent demand is an estimate or bound for customer demand that may have been hidden by stockouts. It is not a replacement for observed sales, and it is not ground truth unless the data source contains independently observed customer requests.

## Available Methods

| Method | Use When | Output |
|---|---|---|
| `flag_exclude` | Inventory evidence is weak or the business prefers conservative training data. | Observed sales, censoring flag, zero training weight for censored rows. |
| `comparable_period` | Similar earlier non-stockout periods exist before the decision date. | Point estimate from historical comparable sales with provenance. |
| `count_likelihood_approx` | A conservative non-negative count approximation is acceptable. | Tail-aware point estimate plus lower and upper bounds. |
| `iterative_impute_refit` | Repeated imputation is needed and convergence can be inspected. | Point estimate and convergence diagnostics. |
| `bounds` | Inventory timing is too uncertain for point imputation. | Lower and upper demand bounds with censored rows excluded from point-target training. |

## Identification Assumptions

- Comparable-period estimates assume earlier non-stockout periods are representative after matching store, product, and promotion state where available.
- Positive end-of-day stock alone does not prove the shelf was available throughout the selling window.
- Stockout flags, stock records, and transaction evidence must be observable by the relevant cutoff.
- Future deliveries, future promotions, and realized after-cutoff inventory events must not be used to estimate pre-order demand.

## Required Provenance Columns

- `observed_sales`
- `is_censored_demand`
- `latent_demand_estimate`
- `latent_demand_lower`
- `latent_demand_upper`
- `latent_demand_provenance`
- `latent_demand_training_weight`

## Fallback

When inventory timing or comparable history is insufficient, use `bounds` or `flag_exclude`. These methods preserve uncertainty and avoid turning weak evidence into a confident training target.
