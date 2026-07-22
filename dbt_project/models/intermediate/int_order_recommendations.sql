with source as (
    select *
    from {{ source('raw_retail', 'scoring_outputs') }}
),

validated as (
    select
        cast(decision_date as date) as decision_date,
        cast(store_id as string) as store_id,
        cast(product_id as string) as product_id,
        cast(model_version as string) as model_version,
        cast(policy_version as string) as policy_version,
        greatest(cast(forecast_q05 as float64), 0.0) as forecast_q05,
        greatest(cast(forecast_q10 as float64), 0.0) as forecast_q10,
        greatest(cast(forecast_q50 as float64), 0.0) as forecast_q50,
        greatest(cast(forecast_q90 as float64), 0.0) as forecast_q90,
        greatest(cast(forecast_q95 as float64), 0.0) as forecast_q95,
        greatest(cast(conformal_adjustment as float64), 0.0) as conformal_adjustment,
        cast(economic_critical_fractile as float64) as economic_critical_fractile,
        greatest(cast(observed_inventory as float64), 0.0) as observed_inventory,
        greatest(cast(pipeline_inventory as float64), 0.0) as pipeline_inventory,
        greatest(cast(recommended_order_quantity as int64), 0) as recommended_order_quantity,
        cast(fallback_used as bool) as fallback_used,
        cast(generated_at as timestamp) as generated_at
    from source
    qualify row_number() over (
        partition by decision_date, store_id, product_id
        order by generated_at desc
    ) = 1
)

select * from validated
