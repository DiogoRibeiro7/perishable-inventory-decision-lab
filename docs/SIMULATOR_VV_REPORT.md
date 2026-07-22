# Simulator Verification And Validation Report

## Status

Software verification: passing for committed invariants and golden scenarios.

Conceptual validity: partially validated. The simulator explicitly represents FIFO stock, deliveries, expiry, shrinkage, lost sales, partial supplier fulfilment, case packs, capacity, and noisy stock records. Event ordering is documented in code and tests, but should be matched against each retailer process before live policy conclusions.

Predictive validity: not validated against real retailer outcomes in this repository. Current evidence is deterministic synthetic execution and hand-solvable fixtures.

## Verification Coverage

- Demand conservation: fulfilled plus lost sales equals demand.
- Stock conservation after arrivals, expiry, and shrinkage: opening stock equals fulfilled units plus ending stock.
- Waste conservation: expiry plus shrinkage equals waste.
- Fulfilment never exceeds demand or opening stock.
- Ending inventory and order quantities remain non-negative.
- Supplier fill never exceeds ordered quantity.
- Identical inputs and seeds reproduce identical event logs.

## Golden Fixture

`tests/fixtures/golden_simulation_expected.csv` records a four-day hand-solvable single-product scenario. `tests/test_simulator_vv.py` compares event-level simulator output against this fixture.

## Calibration Plan

Calibration parameters should be estimated on a separated calibration period and recorded with `build_parameter_manifest`. Required parameter families are demand distribution, lead-time distribution, supplier fill rate, shrinkage, shelf-life distribution, and inventory-record error.

## Sensitivity

Policy comparisons should report KPI intervals from sensitivity runs over uncertain simulator parameters. Dominant assumptions must be named before using simulator output to justify a policy change.

## Gate

`build_validation_gate` provides a machine-readable status. Live policy claims require software verification, conceptual validation, and predictive validation to pass.
