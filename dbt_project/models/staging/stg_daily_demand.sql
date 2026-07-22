with sales as (
    select
        date(sold_at) as date,
        cast(store_id as string) as store_id,
        cast(product_id as string) as product_id,
        sum(quantity) as observed_sales,
        avg(unit_price) as price
    from {{ source('raw_retail', 'daily_sales') }}
    group by 1, 2, 3
),

waste as (
    select
        date(recorded_at) as date,
        cast(store_id as string) as store_id,
        cast(product_id as string) as product_id,
        sum(quantity) as recorded_waste
    from {{ source('raw_retail', 'waste_events') }}
    group by 1, 2, 3
),

promotion as (
    select distinct
        date,
        cast(store_id as string) as store_id,
        cast(product_id as string) as product_id,
        1 as promotion
    from {{ source('raw_retail', 'promotions') }}
)

select
    sales.date,
    sales.store_id,
    sales.product_id,
    greatest(sales.observed_sales, 0) as demand,
    sales.price,
    coalesce(promotion.promotion, 0) as promotion,
    product.shelf_life_days,
    product.lead_time_days,
    product.unit_cost,
    product.unit_margin,
    product.waste_cost,
    coalesce(product.expected_shrinkage_rate, 0.0) as shrinkage_rate,
    coalesce(product.inventory_record_error_std, 0.0) as record_error_std,
    coalesce(waste.recorded_waste, 0) as recorded_waste
from sales
left join waste using (date, store_id, product_id)
left join promotion using (date, store_id, product_id)
inner join {{ source('raw_retail', 'product_master') }} as product
    on sales.product_id = cast(product.product_id as string)
