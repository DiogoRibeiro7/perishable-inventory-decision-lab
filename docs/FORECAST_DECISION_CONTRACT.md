# Forecast-To-Decision Contract

## Purpose

Forecast quality is not enough for replenishment. A forecast object must be compatible with the order cutoff, review period, delivery-time assumption, protection horizon, units, product mapping, inventory belief timestamp, pending orders, constraints, cost/service parameters, and policy version.

## Guardrails

- Marginal daily quantiles must not be added directly across days.
- Policy input requires cumulative horizon distributions or scenario paths with an explicit dependence assumption.
- Stale inventory snapshots are rejected.
- Duplicate pending orders are rejected.
- Unit conversion is explicit and never inferred.
- Every recommendation records forecast version, inventory belief version, policy version, constraints, and binding factors.

## Scenario Paths

Scenario paths can represent temporal dependence. Two sets of marginal daily forecasts can be identical while cumulative risk differs under independent versus comonotonic dependence. The order layer should use the representation that matches the protection horizon.
