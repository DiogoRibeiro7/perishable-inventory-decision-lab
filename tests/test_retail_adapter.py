from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from perishable_lab.data import (
    DailyRetailInputs,
    DataContractError,
    LocalFileRetailAdapter,
    build_canonical_daily_demand,
)


def _base_product_master() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_product_id": "supplier-old",
                "product_id": "P0001",
                "effective_from": "2025-01-01",
                "effective_to": "2025-01-02",
                "shelf_life_days": 4,
                "lead_time_days": 1,
                "unit_cost": 1.0,
                "unit_margin": 2.0,
                "waste_cost": 0.2,
            },
            {
                "source_product_id": "supplier-new",
                "product_id": "P0001",
                "effective_from": "2025-01-03",
                "effective_to": None,
                "shelf_life_days": 4,
                "lead_time_days": 1,
                "unit_cost": 1.0,
                "unit_margin": 2.0,
                "waste_cost": 0.2,
            },
        ]
    )


def _sales() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_primary_key": "sale-1",
                "business_date": "2025-01-01",
                "event_time": "2025-01-01T12:00:00Z",
                "ingestion_time": "2025-01-01T12:05:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "quantity": 5,
            },
            {
                "source_primary_key": "sale-1",
                "business_date": "2025-01-01",
                "event_time": "2025-01-01T12:00:00Z",
                "ingestion_time": "2025-01-01T13:00:00Z",
                "revision": 1,
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "quantity": 7,
            },
            {
                "source_primary_key": "sale-2",
                "business_date": "2025-01-03",
                "event_time": "2025-01-03T12:00:00Z",
                "ingestion_time": "2025-01-03T12:05:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-new",
                "quantity": 3,
            },
        ]
    )


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_date": "2025-01-01",
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "price": 3.0,
                "known_at": "2024-12-31T08:00:00Z",
            },
            {
                "business_date": "2025-01-03",
                "store_id": "S001",
                "source_product_id": "supplier-new",
                "price": 3.1,
                "known_at": "2025-01-02T08:00:00Z",
            },
        ]
    )


def test_local_file_adapter_reads_named_csv_table(tmp_path: Path) -> None:
    expected = pd.DataFrame({"value": [1, 2]})
    expected.to_csv(tmp_path / "sales.csv", index=False)

    adapter = LocalFileRetailAdapter(tmp_path)

    pd.testing.assert_frame_equal(adapter.read_table("sales"), expected)


def test_canonical_builder_deduplicates_revisions_and_preserves_product_lineage() -> None:
    inputs = DailyRetailInputs(
        sales=_sales(),
        product_master=_base_product_master(),
        prices=_prices(),
    )

    first = build_canonical_daily_demand(inputs)
    second = build_canonical_daily_demand(inputs)

    assert first[["date", "store_id", "product_id", "demand"]].equals(
        second[["date", "store_id", "product_id", "demand"]]
    )
    assert first["product_id"].tolist() == ["P0001", "P0001"]
    assert first["demand"].tolist() == [7, 3]
    assert "stockout_flag" in first.columns
    assert first["stockout_flag"].tolist() == [False, False]


def test_canonical_builder_uses_only_promotions_known_by_cutoff() -> None:
    promotions = pd.DataFrame(
        [
            {
                "business_date": "2025-01-01",
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "promotion": 1,
                "known_at": "2025-01-01T10:00:00Z",
            }
        ]
    )
    inputs = DailyRetailInputs(
        sales=_sales().iloc[[0]],
        product_master=_base_product_master(),
        prices=_prices().iloc[[0]],
        promotions=promotions,
    )

    daily = build_canonical_daily_demand(inputs, decision_cutoff_hour=6)

    assert daily.loc[0, "promotion"] == 0


def test_canonical_builder_marks_stock_constrained_sales_as_censored() -> None:
    sales = pd.DataFrame(
        [
            {
                "source_primary_key": "sale-zero-stock",
                "business_date": "2025-01-01",
                "event_time": "2025-01-01T12:00:00Z",
                "ingestion_time": "2025-01-01T12:05:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "quantity": 0,
            },
            {
                "source_primary_key": "sale-low-stock",
                "business_date": "2025-01-03",
                "event_time": "2025-01-03T12:00:00Z",
                "ingestion_time": "2025-01-03T12:05:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-new",
                "quantity": 3,
            },
        ]
    )
    stock_snapshots = pd.DataFrame(
        [
            {
                "source_primary_key": "stock-zero",
                "business_date": "2025-01-01",
                "event_time": "2025-01-01T05:30:00Z",
                "ingestion_time": "2025-01-01T05:35:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-old",
                "on_hand_quantity": 0,
            },
            {
                "source_primary_key": "stock-low",
                "business_date": "2025-01-03",
                "event_time": "2025-01-03T05:30:00Z",
                "ingestion_time": "2025-01-03T05:35:00Z",
                "revision": 0,
                "store_id": "S001",
                "source_product_id": "supplier-new",
                "on_hand_quantity": 2,
            },
        ]
    )
    inputs = DailyRetailInputs(
        sales=sales,
        product_master=_base_product_master(),
        prices=_prices(),
        stock_snapshots=stock_snapshots,
    )

    daily = build_canonical_daily_demand(inputs, decision_cutoff_hour=6)

    zero_stock = daily.loc[daily["date"] == pd.Timestamp("2025-01-01")].iloc[0]
    low_stock = daily.loc[daily["date"] == pd.Timestamp("2025-01-03")].iloc[0]
    assert bool(zero_stock["is_censored_demand"])
    assert zero_stock["censoring_reason"] == "zero_stock"
    assert zero_stock["latent_demand_training_weight"] == 0.0
    assert bool(low_stock["is_censored_demand"])
    assert low_stock["censoring_reason"] == "insufficient_stock"
    assert low_stock["latent_demand_estimate"] == low_stock["observed_sales"]


def test_canonical_builder_fails_closed_on_invalid_critical_fields() -> None:
    product_master = _base_product_master()
    product_master.loc[0, "shelf_life_days"] = 0
    inputs = DailyRetailInputs(
        sales=_sales().iloc[[0]],
        product_master=product_master,
        prices=_prices().iloc[[0]],
    )

    with pytest.raises(DataContractError, match="Shelf life"):
        build_canonical_daily_demand(inputs)
