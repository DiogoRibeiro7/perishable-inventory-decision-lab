# Simulator Card

## Scope

Card version: `simulator-card-v1`

Package version: `0.1.0`

Owner: evaluation

## Purpose

The simulator evaluates perishable inventory policies under explicit assumptions. It is a software test and scenario-analysis tool, not proof of field performance.

## Event Order

For each day, the simulator:

1. Ages and expires stock.
2. Receives due deliveries.
3. Applies shrinkage.
4. Fulfils demand FIFO.
5. Observes noisy inventory.
6. Computes an order request.
7. Applies ordering controls.
8. Applies supplier fill and lead-time jitter.
9. Schedules future arrival.
10. Records cost and state.

Evidence: `tests/test_simulator_vv.py`, `docs/SIMULATOR_VV_REPORT.md`.

## Assumptions And Parameters

Assumptions include FIFO fulfilment, known shelf life, known cost parameters, known supplier fill behavior, explicit shrinkage, and selected inventory-record noise. Calibration parameters should be recorded with the parameter manifest described in `docs/BUSINESS_PARAMETERS.md`.

## Validated Behaviours

- Demand conservation.
- Non-negative orders and inventory.
- Supplier fill never exceeds ordered quantity.
- Identical seeds and inputs reproduce event logs.
- Golden fixture event ordering.

Evidence: `tests/test_inventory.py`, `tests/test_properties.py`, `artifacts/simulator_vv/validation_gate.json`.

## Unvalidated Behaviours

- Real retailer staff behavior.
- True customer substitution.
- Unobserved supplier disruptions.
- Physical shelf-life label accuracy.
- Store-specific receiving and display constraints.

## Limitations

Synthetic conclusions are useful for software validation and sensitivity exploration. They do not establish real retailer impact or production readiness by themselves.
