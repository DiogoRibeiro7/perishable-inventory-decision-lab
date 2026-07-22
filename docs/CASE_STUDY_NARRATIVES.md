# Spoken Narratives

## Five-Minute Version

This project is about fresh-food ordering, where the operational cost of a forecast error depends on shelf life, current stock, lead time, supplier behavior, and store constraints.

I started by making the data grain explicit: one row per store, product, and day, with source contracts and point-in-time feature rules. That matters because grocery data is messy. Product identifiers change, observed sales can be censored by stockouts, inventory records can be stale, and promotions can be revised after a recommendation is generated.

The forecasting layer produces quantiles, not just a point estimate. The decision layer then checks whether the forecast is compatible with the order cutoff, lead time, units, inventory belief, pending orders, and ordering constraints. I separated forecast evaluation from policy evaluation because the model with the best statistical score is not automatically the model that produces the best orders.

The simulator represents FIFO shelf-life cohorts, expiry, shrinkage, pending deliveries, supplier fill, lead-time jitter, and ordering constraints. It is verified with invariants and a hand-solvable golden scenario. I use it as software evidence and scenario analysis, not as proof of retailer impact.

The production path is batch-first. Jobs are idempotent, feature and output artifacts are versioned, recommendation batches are validated before publication, and the active batch is swapped atomically. Monitoring covers data, model, decision, and system failures, with runbooks and rollback.

The key lesson is that the hard part is not fitting a forecast. It is making a recommendation that remains safe when data is late, inventory is wrong, products change, and store operators need to trust and override the output.

## Fifteen-Minute Version

I would present this repository as a decision-system prototype for perishable inventory, not a forecasting notebook.

The problem is fresh-food replenishment. Under-ordering causes stockouts and lost sales. Over-ordering creates waste. The difficulty is that the same forecast error can have different costs depending on shelf life, margin, current stock, delivery timing, case packs, and staff workflow.

The first design choice was to make the data contract explicit. The system validates the store-product-day grain, models product identity changes, treats stockout-censored sales as a first-class issue, and records feature availability timestamps. That lets a training row or recommendation be replayed with the same source partitions and point-in-time features.

The second design choice was to forecast distributions. A replenishment policy often cares about a service quantile or a cumulative horizon distribution, not just the mean. The package fits quantile forecasts, calibrates intervals, checks monotonicity, and rejects invalid forecast-to-decision contracts such as adding marginal daily quantiles without a dependence assumption.

The third design choice was to evaluate the decision itself. The simulator tracks perishable inventory as FIFO cohorts and records the event sequence: expiry, arrivals, shrinkage, fulfilment, noisy stock observation, order request, constraints, supplier fill, and future arrival. The tests check conservation, non-negative quantities, deterministic replay, and golden scenario outputs.

A failure mode I would call out is when a forecast appears better but produces worse orders. If a model improves average error while underestimating the upper tail for short-shelf-life items, a service policy can order too little and create stockouts. Conversely, overestimating demand for constrained products can create avoidable waste. That is why the repo separates pinball loss and interval coverage from fill rate, waste, lost sales, and cost.

The production architecture is batch-first. dbt materializes feature and recommendation marts. Cloud Run Jobs handle scoring and publication. Airflow gates publication. The publication module stages immutable batches and only swaps the active pointer after validation passes. Store-facing readers never see partial batches.

Operationally, the repository includes dashboards, alert rules, incident replay, security role separation, and store-discovery templates. That matters because operators need to know what changed, where, why it matters, and what action is available.

The committed results are synthetic. They show the system can run and expose trade-offs; they do not claim commercial lift. With a retailer, my first 90 days would focus on source contract validation, store workflow discovery, stockout and inventory-error measurement, shadow recommendations, and then a controlled experiment with waste and availability guardrails.
