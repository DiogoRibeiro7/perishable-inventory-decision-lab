# Test Strategy

The test goal is to catch silent numerical, temporal, and inventory-accounting errors. Line coverage is useful only when it supports that goal.

## Layers

| Layer | Coverage focus |
| --- | --- |
| Unit tests | Pure formulas, schema validators, date handling, hash generation, and policy constraints. |
| Property-style tests | Inventory conservation, non-negative quantities, monotone order response, monotone quantiles, deterministic replay, and stable schemas. |
| Metamorphic tests | Future demand revisions must not change earlier features; optimized summaries must match the readable reference path. |
| Golden scenarios | Hand-computable simulation output validates event order, expiry, fulfilment, and cost accounting. |
| Integration tests | Local train-calibrate-score-simulate-publish paths are exercised through existing pipeline, publication, and performance checks. |
| Serialization tests | Manifest hashes, feature-set hashes, active pointers, and store-facing output columns are stable. |
| SQL parity tests | Python and warehouse feature values are compared with tolerance on shared fixtures. |
| Fault injection | Missing rows, late records, duplicates, stale versions, corrupted artifacts, and publish conflicts are tested directly. |
| Mutation checks | Critical modules have a configured mutation target and recorded release gate. |

## Required Properties

- Stock conservation: fulfilled plus lost demand equals demand for every simulated day.
- Non-negative quantities: order, fulfilled, lost, waste, and ending inventory stay non-negative.
- Monotone quantiles: cumulative quantiles stay ordered.
- Deterministic replay: same seed and inputs reproduce outputs.
- Point-in-time correctness: joins use only records effective and available by cutoff.
- No future-state access: revising future demand does not alter earlier lag features.
- Hard constraints: case packs, minimum order quantities, and capacity remain binding.
- Stable output schema: store-facing files expose the same columns in deterministic order.

## CI Split

Fast CI runs all tests except `extended`. Extended CI runs tests marked `extended`; these are allowed to run local benchmarks or larger fixtures. The default local command still runs the full suite unless a marker filter is supplied.

## Release Quality Gate

A release is blocked when any of these fail:

- Ruff and mypy.
- Fast and extended pytest suites.
- Tracked-text hygiene scan.
- Small benchmark budget.
- Feature parity report.
- Golden simulation comparison.
- Publication rollback and corrupted-artifact tests.
- Mutation gate score below the configured threshold.

## Residual Risk

Some failures remain untestable without production-grade data: true supplier incident frequency, staff override behavior, shelf-life label accuracy, unreported stock counts, and local substitutions. Synthetic and hand-computable fixtures cover mechanics, but they cannot prove that real source systems are complete or unbiased.

The coverage and mutation thresholds are meaningful because they are applied to critical modules where small arithmetic or temporal changes can alter store orders. Broad percentage targets alone are not used as release evidence.
