# Performance And Scaling

This benchmark harness measures runtime, memory, throughput, and estimated cloud cost before changing implementation strategy.

## Workloads

| Workload | Stores | Products | Days | Horizons | Quantiles | Scenarios | Policy candidates | Case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| small | 2 | 4 | 80 | 7 | 5 | 100 | 3 | CI regression |
| medium | 10 | 40 | 240 | 14 | 7 | 500 | 5 | local engineering |
| large | 80 | 250 | 540 | 28 | 9 | 1000 | 7 | production planning |
| sparse | 8 | 30 | 240 | 14 | 7 | 500 | 5 | intermittent demand |
| promotion_heavy | 8 | 30 | 240 | 14 | 7 | 500 | 5 | dense commercial calendar |

## Measured Steps

The local benchmark profiles:

- Data ingestion.
- Feature generation.
- Panel summary optimisation.
- Serialization.

Production benchmark extensions should add model fitting, prediction, calibration, scenario generation, simulation, optimisation, BigQuery reads, BigQuery writes, and Cloud Storage artifact movement.

Every step records wall time, CPU time, peak memory, rows per second, series per second, and estimated cloud cost.

## Optimisation Order

1. Remove repeated joins and unnecessary work.
2. Improve data layout and dtypes.
3. Vectorise operations where parity is proven.
4. Batch model calls and I/O.
5. Parallelise independent deterministic work.
6. Add compiled or distributed components only after profiler evidence supports it.

The reference panel summary remains in the package so vectorised changes can be checked for parity.

## Budget Checks

Run:

```bash
poetry run perishable-lab benchmark --workload small --fail-on-budget
```

The small workload budget lives in `configs/performance_budget.example.yaml` and is intentionally loose enough for shared CI machines. Tight release budgets should be calibrated from repeated measurements on pinned hardware.

## Current Scaling Note

For the small workload, the dominant bottleneck is whatever step has the highest measured wall time in `artifacts/benchmark/benchmark_report.json`. For medium and large workloads, do not infer the dominant bottleneck from row counts alone; collect the report first, then decide whether layout, batching, or parallel execution is justified.

Chunked scoring preserves row counts and caps working-set size. Parallel helpers preserve deterministic output order and degrade to the same path when worker count is one.
