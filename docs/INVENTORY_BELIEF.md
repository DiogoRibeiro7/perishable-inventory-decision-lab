# Inventory Belief And Reconciliation

## State Separation

Inventory records are separated into raw recorded events, deterministic reconstructed ledgers, and probabilistic physical-stock beliefs. A stock snapshot is not treated as true physical inventory unless it has been reconciled with deliveries, sales, returns, transfers, waste, expiry, shrinkage, counts, and adjustments.

## Event Ordering

The ledger replays events by `event_time`, then `processing_time`, then `event_id`. Duplicate event IDs are deduplicated by latest revision for replay, while the reconciliation report preserves duplicate-revision warnings.

## Estimators

- Deterministic ledger baseline from event deltas.
- Rule-based reconciliation for negative stock, positive jumps, late revisions, duplicate events, and contradictory counts.
- Particle estimator prototype for hidden physical stock with configurable process and count noise.
- Conservative interval belief when evidence is insufficient.

## Policy Use

Ordering policies should receive inventory from `policy_context_from_belief`. When uncertainty exceeds the configured threshold, the adapter passes the lower inventory bound rather than the mean.
