# Dashboard SQL Examples

## Portfolio Metrics

```sql
select
    business_date,
    safe_divide(sum(waste_units), nullif(sum(ordered_units), 0)) as waste_rate,
    sum(ordered_units) as waste_denominator,
    safe_divide(sum(fulfilled_units), nullif(sum(demand_units), 0)) as availability_rate,
    sum(demand_units) as availability_denominator
from marts.fct_dashboard_daily
where business_date between @start_date and @end_date
group by business_date
order by business_date;
```

## Harmed Segments

```sql
select
    store_id,
    product_id,
    safe_divide(sum(fulfilled_units), nullif(sum(demand_units), 0)) as availability_rate,
    sum(demand_units) as denominator
from marts.fct_dashboard_daily
where business_date between @start_date and @end_date
group by store_id, product_id
having denominator >= @minimum_denominator
   and availability_rate < @availability_threshold
order by availability_rate;
```

## Store/Product Drill-Down

```sql
select
    business_date,
    forecast_p05,
    forecast_p50,
    forecast_p95,
    recommended_order_quantity,
    demand_units,
    fulfilled_units,
    waste_units,
    override_reason
from marts.fct_dashboard_daily
where store_id = @store_id
  and product_id = @product_id
order by business_date;
```
