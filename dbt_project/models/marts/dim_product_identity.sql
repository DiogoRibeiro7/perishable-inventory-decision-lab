{{
    config(
        unique_key=['raw_item_id', 'effective_from', 'known_at'],
        cluster_by=['canonical_product_id', 'demand_entity_id']
    )
}}

select
    raw_item_id,
    sellable_sku_id,
    canonical_product_id,
    demand_entity_id,
    product_family_id,
    category_id,
    supplier_id,
    supplier_item_id,
    unit_of_measure,
    pack_size,
    effective_from,
    effective_to,
    mapping_confidence,
    mapping_status,
    rule_id,
    known_at,
    gtin,
    replacement_for
from {{ ref('stg_product_identity_mappings') }}
where mapping_status in ('accepted', 'rejected', 'pending_review')
