# Ordering Policy Card

## Scope

Card version: `policy-card-v1`

Package version: `0.1.0`

Owner: decision

## Objective

The ordering policy converts compatible forecast distributions, inventory beliefs, pending orders, costs, and constraints into batch order recommendations.

## Inputs

- Cumulative horizon forecast or scenario paths.
- Inventory belief with observed timestamp and unit.
- Pending orders.
- Review period, lead time, shelf life, service quantile.
- Ordering constraints such as case pack, minimum order quantity, and storage capacity.
- Cost parameters and service targets.

Evidence: `tests/test_decision.py`, `tests/test_inventory_optimization.py`, `docs/FORECAST_DECISION_CONTRACT.md`.

## Constraints And Fallbacks

Hard constraints are enforced after the requested quantity is computed. The store-facing system can fall back to the previous valid batch or safe incumbent policy when publication validation fails.

Publication and rollback evidence: `tests/test_publication.py`, `docs/PUBLICATION_RUNBOOK.md`.

## Overrides

Human overrides require store, product, business date, user, quantity, and reason capture. Overrides preserve the original recommendation for audit.

## Sensitivity And Validation

Policy comparisons should include sensitivity to costs, shelf life, supplier fill, hidden inventory, and forecast uncertainty. Robust ordering controls are documented in `docs/INVENTORY_OPTIMIZATION.md` and tested in `tests/test_inventory_optimization.py`.

## Prohibited Uses

- Do not publish recommendations from partial batches.
- Do not use stale inventory snapshots.
- Do not use marginal daily quantiles as cumulative demand without a dependence model.
- Do not claim real-world benefit from synthetic-only results.
- Do not let the same principal approve and publish production policy changes.
