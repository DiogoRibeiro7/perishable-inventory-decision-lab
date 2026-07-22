{{
    config(
        unique_key=['business_date', 'store_id', 'product_id', 'feature_set_version'],
        partition_by={'field': 'business_date', 'data_type': 'date'},
        cluster_by=['store_id', 'product_id', 'feature_set_version']
    )
}}

with demand as (
    select
        date as business_date,
        store_id,
        product_id,
        demand,
        price,
        promotion,
        shelf_life_days,
        lead_time_days,
        recorded_waste
    from {{ ref('stg_daily_demand') }}
),

features as (
    select
        business_date,
        store_id,
        product_id,
        lag(demand, 1) over store_product_order as demand_lag_1,
        lag(demand, 7) over store_product_order as demand_lag_7,
        avg(demand) over store_product_7d as demand_mean_7,
        avg(demand) over store_product_28d as demand_mean_28,
        price,
        promotion,
        shelf_life_days,
        lead_time_days,
        recorded_waste,
        timestamp(business_date) as event_time,
        timestamp(business_date) as effective_time,
        timestamp_add(timestamp(business_date), interval 6 hour) as availability_time,
        current_timestamp() as processing_time,
        'daily-demand-v1' as feature_set_version
    from demand
    window
        store_product_order as (
            partition by store_id, product_id
            order by business_date
        ),
        store_product_7d as (
            partition by store_id, product_id
            order by business_date
            rows between 7 preceding and 1 preceding
        ),
        store_product_28d as (
            partition by store_id, product_id
            order by business_date
            rows between 28 preceding and 1 preceding
        )
)

select *
from features

{% if is_incremental() %}
where business_date >= date_sub(current_date(), interval 35 day)
{% endif %}
