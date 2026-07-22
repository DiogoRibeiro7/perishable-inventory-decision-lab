# Dashboard Wireframes

## Executive/Portfolio

```text
Filters: date range | region | department | rollout stage

Waste rate      Availability      Margin proxy      Acceptance      Rollout status
value + denom   value + denom     value + denom     value + denom   stage + stores

Harmed segments table:
store | product group | metric | value | denominator | threshold | link

Uncertainty:
forecast interval width trend | coverage status | late outcome banner
```

## Customer Success

```text
Affected stores | recurring failure modes | override reasons | supplier issues | recent changes

Store list:
store | issue | sample size | first seen | last seen | runbook | drill-down
```

## Data Science

```text
Calibration | pinball/WIS | bias | drift | segment degradation | fallback rate | comparison

Segment table:
segment | metric | value | denominator | uncertainty | baseline | change | evidence link
```

## Store/Product Drill-Down

```text
Demand history with forecast interval
Stock belief and pending orders
Shelf-life cohorts
Recommendation explanation
Actual sales and waste
Override reason and review history
```

## Operations/On-Call

```text
Pipeline completeness | stale data | publication status | incidents | rollback controls

Alert table:
alert | severity | owner | threshold | sample size | status | drill-down | runbook | fallback
```
