from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from perishable_lab.product_identity import (
    ProductIdentityError,
    ProductIdentityMapping,
    ProductIdentityService,
    RawProductRecord,
    build_review_queue,
    rank_identity_candidates,
)


def _mapping(
    raw_item_id: str,
    canonical_product_id: str,
    demand_entity_id: str,
    *,
    pack_size: float = 1.0,
    known_at: datetime = datetime(2025, 1, 1, tzinfo=UTC),
    effective_from: date = date(2025, 1, 1),
    effective_to: date | None = None,
    status: str = "accepted",
    gtin: str | None = "0001112223333",
) -> ProductIdentityMapping:
    return ProductIdentityMapping(
        raw_item_id=raw_item_id,
        sellable_sku_id=f"SKU-{raw_item_id}",
        canonical_product_id=canonical_product_id,
        demand_entity_id=demand_entity_id,
        product_family_id="F001",
        category_id="C001",
        supplier_id="SUP1",
        supplier_item_id=f"SUP-{raw_item_id}",
        unit_of_measure="each",
        pack_size=pack_size,
        effective_from=effective_from,
        effective_to=effective_to,
        mapping_confidence=0.95,
        mapping_status=status,  # type: ignore[arg-type]
        rule_id="deterministic_gtin",
        known_at=known_at,
        gtin=gtin,
    )


def test_overlapping_effective_dates_for_different_targets_are_rejected() -> None:
    mappings = [
        _mapping("raw-1", "P001", "D001"),
        _mapping("raw-1", "P002", "D002", known_at=datetime(2025, 1, 1, tzinfo=UTC)),
    ]

    with pytest.raises(ProductIdentityError, match="Overlapping accepted mappings"):
        ProductIdentityService(mappings)


def test_pack_size_conflict_prevents_auto_acceptance() -> None:
    source = RawProductRecord(
        raw_item_id="raw-new",
        sellable_sku_id="SKU-new",
        supplier_id="SUP1",
        supplier_item_id="SUP-raw-1",
        category_id="C001",
        product_family_id="F001",
        unit_of_measure="each",
        pack_size=6.0,
        gtin="0001112223333",
    )

    candidates = rank_identity_candidates(source, [_mapping("raw-1", "P001", "D001", pack_size=1.0)])

    assert candidates[0].review_action == "needs_review"
    assert "pack_size" not in candidates[0].reasons


def test_ambiguous_candidates_go_to_review_queue() -> None:
    source = RawProductRecord(
        raw_item_id="raw-new",
        sellable_sku_id="SKU-new",
        supplier_id="SUP1",
        supplier_item_id="SUP-raw-new",
        category_id="C001",
        product_family_id="F001",
        unit_of_measure="each",
        pack_size=1.0,
        gtin="same",
    )
    mappings = [
        _mapping("raw-1", "P001", "D001", gtin="same"),
        _mapping("raw-2", "P002", "D002", gtin="same"),
    ]

    candidates = rank_identity_candidates(source, mappings)
    queue = build_review_queue(candidates)

    assert candidates[0].ambiguous
    assert len(queue) == 2


def test_late_remapping_preserves_historical_reproducibility() -> None:
    mappings = [
        _mapping("raw-1", "P001", "D001", known_at=datetime(2025, 1, 1, tzinfo=UTC)),
        _mapping("raw-1", "P002", "D002", known_at=datetime(2025, 2, 1, tzinfo=UTC)),
    ]
    service = ProductIdentityService(mappings)

    historical = service.resolve(
        "raw-1",
        business_date="2025-01-15",
        known_at="2025-01-20T00:00:00Z",
    )
    restated = service.resolve(
        "raw-1",
        business_date="2025-01-15",
        known_at="2025-02-02T00:00:00Z",
    )

    assert historical.demand_entity_id == "D001"
    assert restated.demand_entity_id == "D002"


def test_deterministic_matching_order_is_stable() -> None:
    source = RawProductRecord(
        raw_item_id="raw-new",
        sellable_sku_id="SKU-new",
        supplier_id="SUP1",
        supplier_item_id="SUP-raw-new",
        category_id="C001",
        product_family_id="F001",
        unit_of_measure="each",
        pack_size=1.0,
        gtin="same",
    )
    mappings = [
        _mapping("raw-b", "P002", "D002", gtin="same"),
        _mapping("raw-a", "P001", "D001", gtin="same"),
    ]

    first = rank_identity_candidates(source, mappings)
    second = rank_identity_candidates(source, list(reversed(mappings)))

    assert [candidate.candidate_raw_item_id for candidate in first] == [
        candidate.candidate_raw_item_id for candidate in second
    ]


def test_category_only_match_is_rejected() -> None:
    source = RawProductRecord(
        raw_item_id="raw-new",
        sellable_sku_id="SKU-new",
        supplier_id="SUP9",
        supplier_item_id="unknown",
        category_id="C001",
        product_family_id="F999",
        unit_of_measure="case",
        pack_size=12.0,
        gtin=None,
    )

    candidates = rank_identity_candidates(source, [_mapping("raw-1", "P001", "D001")])

    assert candidates[0].review_action == "reject"
    assert candidates[0].confidence == 0.05
