# Dashboard Semantic Layer

Grain: `store_id`, `product_id`, `business_date`.

Primary mart: `dbt_project/models/marts/fct_dashboard_daily.sql`.

## Fields

| Field | Source | Freshness | Access |
| --- | --- | ---: | --- |
| `business_date` | `fct_dashboard_daily` | 24h | Portfolio |
| `store_id` | `fct_dashboard_daily` | 24h | Store |
| `product_id` | `fct_dashboard_daily` | 24h | Store |
| `forecast_p05` | `fct_dashboard_daily` | 6h | Store |
| `forecast_p50` | `fct_dashboard_daily` | 6h | Store |
| `forecast_p95` | `fct_dashboard_daily` | 6h | Store |
| `recommended_order_quantity` | `fct_dashboard_daily` | 6h | Store |
| `override_reason` | Publication and review logs | 6h | Restricted |
| `waste_units` | Waste records | 48h | Store |
| `fulfilled_units` | Sales and demand reconstruction | 48h | Store |
| `incident_count` | Monitoring logs | 1h | Portfolio |

## Access Assumptions

Portfolio users can see aggregates. Store users see only allowed `store_id` rows. Restricted fields such as override reason are visible only to roles with operations review or audit access.

## Consistency Rules

- Aggregates must equal the sum of drill-down numerators and denominators.
- Segment views must show sample size and denominator.
- Filters must apply before metric aggregation.
- Late outcomes must not be mixed with leading indicators.
- Every alert links to a drill-down URL and runbook.
