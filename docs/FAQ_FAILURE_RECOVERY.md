# FAQ and Failure Recovery

## What if the demo command fails?

Use the committed artifacts in [`reports/example_run`](../reports/example_run). They are sufficient to discuss calibration, policy tradeoffs, and monitoring without running local training.

## What if Poetry is missing?

Install dependencies with Poetry for the supported path. The package is ordinary Python, but the release commands and CI use Poetry for repeatability.

## What if cloud credentials are unavailable?

Use the local demo. Cloud resources in `gcp`, `dbt_project`, and `airflow` are deployment examples and are not required for portfolio review.

## What if the model undercovers one segment?

Treat the global metric as insufficient. Add segment-level calibration checks by promotion status, shelf life, store, product, and demand volume before expanding usage.

## What if observed sales are capped by stockouts?

Do not train as if observed sales always equal demand. Use the censored-demand utilities as a starting point, then validate assumptions with stock, lost-sales, and substitution evidence.

## What if inventory records are unreliable?

Reconcile observed stock with expected stock before publishing recommendations. If uncertainty remains high, widen buffers or hold publication until the source issue is resolved.

## What if the recommended quantity is operationally invalid?

The publication path validates non-negative quantities, required metadata, expected units, and batch completeness. Invalid batches should fail before publication and retain the previous valid batch.
