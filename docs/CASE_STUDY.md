# Interview Case-Study Walkthrough

## One-minute summary

This project treats fresh-food replenishment as a decision problem under two coupled uncertainties: future demand and current inventory. It generates realistic store-product demand, estimates multiple demand quantiles, calibrates the forecast interval, simulates age-structured inventory, and compares ordering policies using waste, availability, lost sales, and total cost.

## Five-minute technical narrative

1. **Data integrity first.** The pipeline validates the store-product-day grain and rejects duplicated or invalid records before modelling.
2. **Leakage-safe features.** Demand lags and rolling statistics are shifted so each row uses only information available when the order is placed.
3. **Distributional forecast.** Separate gradient-boosting models estimate quantiles from 5% to 95%. Predictions are forced to remain ordered.
4. **Calibration.** A later calibration interval produces a conformal expansion. The final test interval remains untouched.
5. **Inventory simulation.** Stock is stored in shelf-life cohorts. Sales are FIFO; expiry, shrinkage, lead time, and inventory-record noise are explicit.
6. **Policy comparison.** A median baseline is compared with fixed service-level and economic newsvendor policies.
7. **Operational selection.** The best model is not automatically the lowest statistical loss. The preferred policy must satisfy availability constraints and minimise business cost.

## Questions I would investigate with real data

- How is lost demand inferred when sales are censored by stockouts?
- Can waste, shrinkage, and scanning errors be separated reliably?
- At what hierarchy should cold-start products borrow information?
- Are order acceptances a clean label, or are they influenced by staff trust and workload?
- Which constraints are hard rules: case packs, delivery schedules, display minimums, supplier availability, or storage capacity?
- How quickly do product IDs and supplier mappings change?

## What I would build next

The next version would estimate multi-horizon joint or marginal demand distributions, add stockout-censoring correction, represent product identity through a hierarchy or learned embedding, and optimise a constrained policy over lead time and shelf-life cohorts. I would deploy it in shadow mode first and measure operational lift by store and product segment.
