# Card Release Checklist

Update the relevant card before release when any of these change:

- Forecast target, horizon, model version, feature set, calibration method, or metric artifact.
- Policy objective, costs, service constraints, state inputs, fallback, or override process.
- Simulator event order, calibrated parameters, assumptions, invariants, or validation reports.
- System architecture, lineage, publication process, monitoring, rollback, security, or environment boundaries.
- Any public claim, limitation, assumption, or prohibited use.

Release gate:

- Validate card metadata.
- Confirm every metric links to an artifact path and field.
- Confirm every claim links to a test, report, artifact, or registered assumption.
- Confirm run manifest package version and artifact versions match card metadata.
- Confirm changed interfaces are listed in at least one card.
- Confirm no card claims real retailer impact from synthetic-only evidence.
