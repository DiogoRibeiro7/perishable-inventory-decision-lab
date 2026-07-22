# Public Retail Benchmark Artifacts

This directory stores small reproducible benchmark summaries. Raw public competition data is not committed.

To regenerate full local artifacts, place user-provided M5 CSV files in `data/raw/m5` and run:

```bash
poetry run perishable-lab public-retail-benchmark data/raw/m5 --output-dir artifacts/public-retail-benchmark
```

The committed result table below is a schema example from the CI fixture, not a claim about full M5 performance.
