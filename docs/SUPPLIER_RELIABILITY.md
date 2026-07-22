# Supplier Lead Time And Delivery Reliability

## Semantics

Supplier reliability data separates order creation, cutoff, acknowledgement, requested delivery, dispatch, arrival, receiving completion, accepted quantity, rejected quantity, cancellation, and revision. Forecasts generated before arrival must not use actual arrival or receiving completion information.

Calendar time is separate from valid delivery days. Weekend and holiday crossings should use a delivery calendar when contractual lead time is expressed in open delivery days.

## Models

- `ContractualLeadTimeModel`: deterministic baseline for new or sparse lanes.
- `EmpiricalLeadTimeModel`: supplier-product lead-time support, fill-rate expectation, cancellation probability, and rejection probability.
- Supplier-shock detection: rolling fill-rate and late-rate checks trigger fallback handling for deteriorating suppliers.

## Recommendation Metadata

Every recommendation should include the assumed lead-time support, probabilities, expected fill rate, cancellation probability, rejection probability, source, and reliability version.

## Monitoring Specification

Track fill rate, late rate, cancellation rate, rejection rate, lead-time quantile loss, calibration by supplier/product lane, and service/waste impact after supplier shocks.
