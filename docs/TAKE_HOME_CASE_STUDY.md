# Take-Home Case Study

This exercise evaluates practical reasoning for fresh-grocery forecasting and ordering under imperfect data. It is deliberately compact: the goal is a correct baseline, clear assumptions, and defensible trade-offs rather than a large modelling platform.

Run the reference path with:

```bash
poetry run python -m case_study.run --output artifacts/take_home_case_study
```

## Problem Statement

You receive daily fresh-grocery files for sales, inventory snapshots, deliveries, waste, prices, promotions, and product metadata. Build a small solution that recommends replenishment quantities for the holdout period.

Your solution should:

- Audit the input data and state assumptions.
- Build a leakage-safe baseline forecast or uncertainty estimate.
- Convert uncertainty into an ordering recommendation.
- Evaluate forecast and operating metrics.
- Explain how the solution would move toward production.
- State limitations honestly.

The evaluator has a hidden demand file used only for scoring. Treat it as unavailable to the candidate workflow.

## Dataset

The generator writes:

| File | Purpose |
| --- | --- |
| `sales.csv` | Daily sold units, stockout flag, transaction count, and record availability time. |
| `inventory_snapshots.csv` | Morning observed inventory with one deliberate negative count. |
| `deliveries.csv` | Received and ordered quantities. |
| `waste.csv` | Recorded expiry waste. |
| `prices.csv` | Price records known before the planning cutoff. |
| `promotions.csv` | Promotion records, including one late-known row that should be excluded. |
| `products.csv` | Shelf life, lead time, unit economics, pack size, minimum order, and capacity. |
| `evaluator_only/hidden_truth.csv` | True demand used only by the evaluator. |

Intentional issues include a duplicated sales key, a negative transaction count, a negative stock snapshot, late promotion availability, censored sales under stockout, and sparse waste observations.

## Candidate Instructions

Submit a runnable solution that writes:

- `recommendations.csv` with `date`, `store_id`, `product_id`, and `recommended_order_units`.
- `metrics.json` with forecast and operating metrics.
- `audit_assumptions.md` explaining data fixes, modelling choices, and limitations.

The recommended scope is:

- Clean duplicated daily keys by taking the latest known record.
- Use only records available by the planning cutoff.
- Split by date, not by shuffled rows.
- Start with a seasonal empirical baseline.
- Use a service quantile or conservative interval as the order-up-to target.
- Enforce non-negative quantities, pack size, minimum order, and storage capacity.
- Keep hidden truth out of training and recommendation files.

## Reference Solution

The reference solution in `case_study/reference_solution.py` deliberately prioritises correctness over modelling breadth:

- Deduplicates sales records by date, store, product, and latest availability time.
- Clips impossible negative operational values and documents the assumption.
- Filters prices and promotions to the 06:00 planning cutoff.
- Trains `SeasonalNaiveQuantileForecaster` on the training period only.
- Converts an 80th percentile baseline into constrained order quantities.
- Scores the holdout period against evaluator-only truth after recommendations are produced.

## Evaluator Rubric

| Area | Weight | Strong answer |
| --- | ---: | --- |
| Problem framing | 10 | Defines the decision, horizon, cutoff, and success metrics before modelling. |
| Data correctness | 15 | Finds duplicate, negative, late-known, and censored records with explicit handling. |
| Statistical reasoning | 15 | Uses a time-based split and uncertainty-aware baseline without leakage. |
| Inventory logic | 15 | Applies lead time, stock position, capacity, minimum order, and pack constraints. |
| Evaluation | 15 | Separates forecast metrics from fill, waste, lost sales, and cost. |
| Software quality | 10 | Provides a small runnable path with deterministic outputs and tests. |
| Communication | 10 | Explains trade-offs in plain operational language. |
| Honesty | 10 | Avoids unsupported impact claims and names what cannot be inferred. |

Hidden checks cover leakage, stock conservation, duplicate recommendation keys, and recommendation constraints.

## Presentation Outline

1. Decision framing: what order is being made, when, and under which constraints.
2. Data audit: issues found, fixes applied, and unresolved risks.
3. Baseline design: time split, seasonal empirical quantiles, and cutoff-safe features.
4. Ordering rule: service target, inventory position, and constraints.
5. Results: fill, waste, lost sales, cost, and where the baseline fails.
6. Production path: contracts, monitoring, rollback, and store feedback.
7. Limitations: synthetic scope, censored demand, missing substitutions, and calibration by segment.

## 30-Minute Defence Questions

1. What information is available at the ordering cutoff?
2. Why is a shuffled train-test split invalid here?
3. How did you handle duplicated daily sales rows?
4. Why is hidden true demand excluded from recommendation files?
5. What would change if stockout flags were unreliable?
6. Which metric would you prioritise for short shelf-life products?
7. How does pack size change the forecast-to-order conversion?
8. When can a better median forecast worsen fill rate?
9. What monitoring checks would block publication?
10. How would you validate this with one pilot store?
11. What failure would you expect during a promotion week?
12. What would you add if you had four more hours?
13. How would you explain waste and availability trade-offs to store operators?
14. Which assumption most affects the result?
15. What makes the reference solution intentionally limited?
