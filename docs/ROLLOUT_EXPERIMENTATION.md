# Rollout Experimentation

This protocol moves ordering changes from offline evidence into shadow runs, reviewed use, limited pilots, controlled field tests, and progressive rollout. Each stage has explicit evidence gates, telemetry, stop authority, and a safe return to the incumbent ordering policy.

## Stage Gates

| Stage | Impact | Entry evidence | Exit evidence | Stop authority |
| --- | --- | --- | --- | --- |
| Historical replay | None | Frozen inputs, known incumbent actions, validated simulator | Offline estimate passes guardrails and sensitivity bounds | Experiment owner, operations lead |
| Shadow | None | Telemetry contract deployed, daily comparison dashboard | No critical missing telemetry, candidate decisions generated on schedule | Experiment owner, operations lead, platform owner |
| Human review | None until accepted | Shadow guardrails passed, review workflow staffed | Acceptance threshold met, override reasons reviewed weekly | Store operations lead, experiment owner |
| Limited pilot | Small live scope | Store roster approved, rollback rehearsed | Availability, waste, and incident guardrails pass | Operations lead, commercial owner, on-call owner |
| Field test | Registered test scope | Assignment table published, baseline locked, power check approved | Primary estimand passes, no sample-ratio alert, clustered uncertainty reported | Experiment owner, analytics owner, operations lead |
| Progressive rollout | Ramped live scope | Field-test decision log approved, support team ready | Guardrails pass at each ramp with no unresolved incident | Operations lead, commercial owner, platform owner |

## Experimental Design

Choose the assignment unit by the strongest credible interference path:

| Interference risk | Preferred unit |
| --- | --- |
| Staff learning, ordering routines, shared receiving labor | Store |
| Shared displays, department labor, local substitution | Department |
| Product substitution and pack-family effects | Product cluster |
| Strong seasonality or operational calendar constraints | Time block or stepped-wedge |

The baseline period must be locked before assignment publication and must cover the normal replenishment cycle plus representative weekly demand. Power calculations should be written in the decision log with the minimum detectable effect on `balanced_loss`, defined as `(1 - availability_rate) + waste_rate`. A candidate may not improve this primary metric by causing availability or waste to breach its standalone guardrail.

Duration should cover at least two order-review cycles and a full supplier cadence. Seasonality, holidays, promotions, staff training, supplier capacity, shared displays, local substitutes, and store fairness strata must be listed before launch.

## Outcomes

Primary outcome:

- `balanced_loss = (1 - availability_rate) + waste_rate`

Guardrails:

- Availability drop versus incumbent.
- Waste-rate increase versus incumbent.
- Staff acceptance and override reasons.
- Order volatility.
- Revenue and margin.
- Operational incidents.
- Fairness across stores, measured as the largest store-level degradation gap.

## Analysis Plan

The decision log must pre-register:

- Estimand: average effect of activating the candidate policy for the assigned unit during the analysis window.
- Exclusions: stores closed for abnormal periods, products without publishable inventory signals, and rows with unresolved identity mapping.
- Covariates: baseline margin, baseline waste, baseline availability, store format, department, supplier cadence, and seasonality indicators.
- Missing outcomes: report missingness by group, fail the gate when critical telemetry is absent, and do not impute primary outcomes without a sensitivity table.
- Uncertainty: cluster by assignment unit and report the clustering level.
- Monitoring: review guardrails on a schedule agreed before launch; do not stop for favorable interim movement alone.
- Multiple metrics: the primary metric decides benefit, guardrails decide safety, and supporting metrics explain tradeoffs.
- Adjustment: use CUPED-style or other covariate adjustment only when covariates are measured before assignment and are balanced enough for interpretation.

## Telemetry Contract

Every live row must include:

- `experiment_id`
- `assignment_unit`
- `assignment_group`
- `business_date`
- `store_id`
- `product_id`
- `incumbent_order_units`
- `candidate_order_units`
- `active_order_units`
- `published_policy`
- `availability_rate`
- `waste_rate`
- `revenue`
- `margin`
- `override_reason`
- `incident_count`

Assignment tables must include `experiment_id`, `assignment_unit`, `assignment_group`, and `assignment_score`. Publish the manifest checksum before launch and keep it immutable for analysis.

## Deliverables

- Experiment protocol: stage, assignment unit, baseline, duration, minimum detectable effect, estimand, guardrails, exclusions, covariates, uncertainty method, and stop authority.
- Rollout checklist: evidence gate, support coverage, dashboard links, rollback rehearsal, communications, and post-launch review.
- Telemetry contract: required columns and non-null fields.
- Assignment table design: stable salted hash by assignment unit with immutable manifest checksum.
- Analysis notebook: call package functions for assignment checks, telemetry validation, guardrail decisions, and outcome summaries.
- Decision log: all approvals, deviations, monitoring decisions, and final action.
- Rollback runbook: freeze ramp, set active policy to incumbent, republish incumbent quantities, notify operations, archive evidence.

## Safe Return

Any named stop authority can pause or stop the test. If a rollback guardrail fires, the active recommendation stream reverts by setting `published_policy` to `incumbent`, publishing incumbent quantities for pending order cycles, freezing ramp changes, and archiving the assignment, telemetry, guardrail, and decision-log snapshots.
