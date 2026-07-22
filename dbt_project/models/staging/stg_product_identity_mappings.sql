with source as (
    select *
    from {{ source('raw_retail', 'product_identity_mappings') }}
),

validated as (
    select
        cast(raw_item_id as string) as raw_item_id,
        cast(sellable_sku_id as string) as sellable_sku_id,
        cast(canonical_product_id as string) as canonical_product_id,
        cast(demand_entity_id as string) as demand_entity_id,
        cast(product_family_id as string) as product_family_id,
        cast(category_id as string) as category_id,
        cast(supplier_id as string) as supplier_id,
        cast(supplier_item_id as string) as supplier_item_id,
        cast(unit_of_measure as string) as unit_of_measure,
        cast(pack_size as float64) as pack_size,
        cast(effective_from as date) as effective_from,
        cast(effective_to as date) as effective_to,
        cast(mapping_confidence as float64) as mapping_confidence,
        cast(mapping_status as string) as mapping_status,
        cast(rule_id as string) as rule_id,
        cast(known_at as timestamp) as known_at,
        cast(gtin as string) as gtin,
        cast(replacement_for as string) as replacement_for
    from source
)

select *
from validated
where mapping_confidence between 0.0 and 1.0
