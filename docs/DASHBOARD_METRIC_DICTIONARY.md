# Dashboard Metric Dictionary

| Metric | View | Numerator | Denominator | Timing | Threshold | Action |
| --- | --- | --- | --- | --- | ---: | --- |
| Waste rate | Executive/portfolio | `waste_units` | `ordered_units` | Outcome | 0.08 | Open affected stores |
| Availability rate | Executive/portfolio | `fulfilled_units` | `demand_units` | Outcome | 0.95 | Inspect harmed segments |
| Margin proxy per unit | Executive/portfolio | `margin_proxy` | `demand_units` | Outcome | n/a | Review product mix |
| Acceptance rate | Customer success | `accepted_count` | `recommendation_count` | Leading | 0.80 | Review override reasons |
| Forecast interval width | Data science | `forecast_width_sum` | `forecast_count` | Leading | n/a | Inspect calibration |
| Fallback rate | Data science | `fallback_count` | `recommendation_count` | Leading | 0.05 | Review fallback drivers |
| Publication completeness | Operations/on-call | `published_rows` | `expected_rows` | Leading | 1.00 | Hold publication if incomplete |

Every metric must display denominator and sample size. Outcome metrics are hidden from final judgement until `outcome_available_at` has passed. Leading metrics can be used to hold publication before outcomes arrive.
