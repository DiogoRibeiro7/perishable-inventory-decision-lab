{{
    config(
        unique_key=['business_date', 'store_id', 'product_id'],
        partition_by={'field': 'business_date', 'data_type': 'date'},
        cluster_by=['store_id', 'product_id']
    )
}}

with recommendations as (
    select
        decision_date as business_date,
        store_id,
        product_id,
        forecast_q05 as forecast_p05,
        forecast_q50 as forecast_p50,
        forecast_q95 as forecast_p95,
        recommended_order_quantity,
        policy_version,
        model_version,
        generated_at
    from {{ ref('fct_daily_order_decisions') }}
),

features as (
    select
        business_date,
        store_id,
        product_id,
        demand_lag_1,
        demand_mean_7,
        demand_mean_28,
        promotion,
        shelf_life_days,
        lead_time_days
    from {{ ref('fct_feature_set_daily') }}
),

joined as (
    select
        recommendations.business_date,
        recommendations.store_id,
        recommendations.product_id,
        recommendations.forecast_p05,
        recommendations.forecast_p50,
        recommendations.forecast_p95,
        recommendations.recommended_order_quantity,
        recommendations.policy_version,
        recommendations.model_version,
        recommendations.generated_at,
        features.demand_lag_1,
        features.demand_mean_7,
        features.demand_mean_28,
        features.promotion,
        features.shelf_life_days,
        features.lead_time_days,
        greatest(recommendations.forecast_p95 - recommendations.forecast_p05, 0) as forecast_interval_width,
        1 as recommendation_count,
        1 as published_rows,
        1 as expected_rows
    from recommendations
    left join features
        on recommendations.business_date = features.business_date
        and recommendations.store_id = features.store_id
        and recommendations.product_id = features.product_id
)

select *
from joined

{% if is_incremental() %}
where business_date >= date_sub(current_date(), interval 35 day)
{% endif %}
