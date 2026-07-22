{{
    config(
        unique_key=['decision_date', 'store_id', 'product_id'],
        partition_by={'field': 'decision_date', 'data_type': 'date'},
        cluster_by=['store_id', 'product_id']
    )
}}

select
    cast(decision_date as date) as decision_date,
    cast(store_id as string) as store_id,
    cast(product_id as string) as product_id,
    cast(model_version as string) as model_version,
    cast(policy_version as string) as policy_version,
    forecast_q05,
    forecast_q10,
    forecast_q50,
    forecast_q90,
    forecast_q95,
    conformal_adjustment,
    economic_critical_fractile,
    observed_inventory,
    pipeline_inventory,
    recommended_order_quantity,
    fallback_used,
    generated_at
from {{ ref('int_order_recommendations') }}

{% if is_incremental() %}
where decision_date >= date_sub(current_date(), interval 3 day)
{% endif %}
