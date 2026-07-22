# Failure Analysis and Error Taxonomy

Aggregate metrics can hide the exact mechanism behind a bad replenishment outcome. The diagnostics in `src/perishable_lab/failures.py` create row-level records, aggregate them into recurring episodes, and rank cohorts by operating impact.

Run the diagnostic CLI with:

```bash
poetry run perishable-lab diagnose-failures input.csv --output-dir artifacts/failure-analysis --mode post_outcome
```

Use `--mode real_time` before outcomes are complete. That mode ignores realised demand, interval misses, waste, fulfilled units, and lost sales so the investigation cannot accidentally depend on post-outcome information.

## Taxonomy

| Cause | Typical evidence | Proposed change |
| --- | --- | --- |
| Missing or late data | Missing source count or source latency breach | Add freshness gates and quarantine late partitions before scoring. |
| Product-mapping error | Low mapping confidence or high mapping churn | Add identity regression fixtures and mapping review. |
| Promotion or event surprise | Event not known by cutoff or event surprise flag | Track event availability and add cutoff-safe revision tests. |
| Stockout-censored target | Stockout evidence after outcomes | Separate observed sales from latent-demand estimates. |
| Inventory-state error | Large stock gap before ordering | Reconcile snapshots with sales, deliveries, shrinkage, and waste. |
| Supplier disruption | Fill rate below target or supplier exception | Join supplier exception data before publication. |
| Shelf-life misspecification | Observed shelf life differs from expected life | Validate shelf life by product, supplier, and receiving condition. |
| Cold start or structural break | Sparse history or shift score | Route through hierarchy-aware fallback and segment monitoring. |
| Tail undercoverage | Actual demand exceeds upper interval | Calibrate intervals by segment and gate affected cohorts. |
| Constraint or policy error | Pack, capacity, or minimum order violation | Add constraint fixtures and publication validation. |
| Human override or workflow mismatch | Structured override reason | Review store workflow evidence without assigning blame. |
| Publication/system failure | Failed or stale publication status | Hold publication, replay the run, and add idempotence checks. |
| Unknown | No strong configured signal | Create a minimal reproduction and collect missing context. |

## Output Files

The CLI writes:

- `failure_records.csv`: one row per diagnosed store-product-date.
- `failure_episodes.csv`: recurring store-product-cause cohorts ranked by impact.
- `top_failure_report.md`: top cohorts, paired forecast-versus-decision analysis, and representative case studies.
- `root_cause_workflow.json`: repeatable investigation steps.

## Paired Analysis

The report separates statistical error from decision error:

- A forecast can be statistically poor while the final order remains acceptable because inventory, capacity, or pack constraints absorb the miss.
- A small forecast error can create high cost when it lands near a case-pack threshold, capacity limit, short shelf-life risk, or a high-margin stockout.

This keeps the investigation focused on the decision pathway rather than defaulting to a generic model change.

## Root-Cause Workflow

1. Freeze the affected data, forecast, recommendation, and outcome partitions.
2. Generate row diagnostics in both post-outcome and real-time modes.
3. Rank cohorts by operating impact, then inspect representative rows.
4. Confirm whether each candidate cause has source evidence or only correlation.
5. Create a regression fixture from confirmed records and expected diagnostics.
6. Add or adjust a data contract, monitoring gate, policy constraint, or calibration check.
7. Close the incident only when the fixture fails before the change and passes after it.
