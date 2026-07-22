"""Build the canonical store-product-day panel from retail source tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

import numpy as np
import pandas as pd

from perishable_lab.data.validation import validate_daily_demand


class DataContractError(ValueError):
    """Raised when source data cannot be mapped to the canonical contract."""


@dataclass(frozen=True)
class DailyRetailInputs:
    """Source tables required to build a daily store-product panel."""

    sales: pd.DataFrame
    product_master: pd.DataFrame
    prices: pd.DataFrame
    stock_snapshots: pd.DataFrame | None = None
    waste_events: pd.DataFrame | None = None
    promotions: pd.DataFrame | None = None


def deduplicate_versioned_events(frame: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Keep the latest revision for each source primary key."""
    required = {"source_primary_key", "revision", "ingestion_time"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"{table_name} is missing columns: {missing}")

    prepared = frame.copy()
    prepared["revision"] = prepared["revision"].astype(int)
    prepared["ingestion_time"] = pd.to_datetime(prepared["ingestion_time"], utc=True)
    return (
        prepared.sort_values(["source_primary_key", "revision", "ingestion_time"])
        .drop_duplicates("source_primary_key", keep="last")
        .reset_index(drop=True)
    )


def _empty_or_copy(frame: pd.DataFrame | None) -> pd.DataFrame:
    return pd.DataFrame() if frame is None else frame.copy()


def _require_columns(frame: pd.DataFrame, required: set[str], table_name: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"{table_name} is missing columns: {missing}")


def _normalise_business_date(frame: pd.DataFrame) -> pd.DataFrame:
    normalised = frame.copy()
    normalised["business_date"] = pd.to_datetime(normalised["business_date"]).dt.normalize()
    return normalised


def _decision_cutoff(frame: pd.DataFrame, cutoff_hour: int) -> pd.Series:
    return frame["business_date"] + pd.Timedelta(hours=cutoff_hour)


def _filter_known_by_cutoff(
    frame: pd.DataFrame,
    *,
    known_at_column: str,
    cutoff_hour: int,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    _require_columns(frame, {"business_date", known_at_column}, "known source table")
    prepared = _normalise_business_date(frame)
    known_at = pd.to_datetime(prepared[known_at_column], utc=True).dt.tz_convert(None)
    prepared[known_at_column] = known_at
    return prepared.loc[known_at <= _decision_cutoff(prepared, cutoff_hour)].reset_index(drop=True)


def _map_products(events: pd.DataFrame, product_master: pd.DataFrame, table_name: str) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    _require_columns(events, {"business_date", "source_product_id"}, table_name)
    _require_columns(
        product_master,
        {
            "source_product_id",
            "product_id",
            "effective_from",
            "shelf_life_days",
            "lead_time_days",
            "unit_cost",
            "unit_margin",
            "waste_cost",
        },
        "product_master",
    )

    left = _normalise_business_date(events)
    left["_source_row_id"] = range(len(left))
    master = product_master.copy()
    master["effective_from"] = pd.to_datetime(master["effective_from"]).dt.normalize()
    if "effective_to" in master.columns:
        master["effective_to"] = pd.to_datetime(master["effective_to"]).dt.normalize()
    else:
        master["effective_to"] = pd.NaT

    mapped = left.merge(master, on="source_product_id", how="left", suffixes=("", "_master"))
    active = (mapped["business_date"] >= mapped["effective_from"]) & (
        mapped["effective_to"].isna() | (mapped["business_date"] <= mapped["effective_to"])
    )
    mapped = (
        mapped.loc[active]
        .sort_values(["_source_row_id", "effective_from"])
        .drop_duplicates("_source_row_id", keep="last")
        .drop(columns=["_source_row_id"])
        .reset_index(drop=True)
    )
    if mapped["product_id"].isna().any() or len(mapped) != len(left):
        raise DataContractError(f"{table_name} contains unmapped product records")
    return mapped


def _aggregate_sales(sales: pd.DataFrame, product_master: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        sales,
        {"business_date", "store_id", "source_product_id", "quantity"},
        "sales",
    )
    mapped = _map_products(_normalise_business_date(sales), product_master, "sales")
    daily = (
        mapped.groupby(["business_date", "store_id", "product_id"], as_index=False)
        .agg(
            demand=("quantity", "sum"),
            observed_sales=("quantity", "sum"),
            source_product_ids=("source_product_id", lambda values: "|".join(sorted(set(map(str, values))))),
            shelf_life_days=("shelf_life_days", "first"),
            lead_time_days=("lead_time_days", "first"),
            unit_cost=("unit_cost", "first"),
            unit_margin=("unit_margin", "first"),
            waste_cost=("waste_cost", "first"),
        )
        .rename(columns={"business_date": "date"})
    )
    return daily


def _latest_by_key(frame: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sort_columns = ["business_date", "store_id", "product_id"]
    if "known_at" in frame.columns:
        sort_columns.append("known_at")
    if "ingestion_time" in frame.columns:
        sort_columns.append("ingestion_time")
    deduped = frame.sort_values(sort_columns).drop_duplicates(
        ["business_date", "store_id", "product_id"],
        keep="last",
    )
    return deduped[["business_date", "store_id", "product_id", *value_columns]]


def _stock_daily(inputs: DailyRetailInputs, *, cutoff_hour: int) -> tuple[pd.DataFrame, bool]:
    stock = _empty_or_copy(inputs.stock_snapshots)
    columns = [
        "business_date",
        "store_id",
        "product_id",
        "observed_inventory",
        "late_stock_snapshot",
    ]
    if stock.empty:
        return pd.DataFrame(columns=columns), False

    stock = deduplicate_versioned_events(stock, "stock_snapshots")
    stock = _map_products(_normalise_business_date(stock), inputs.product_master, "stock_snapshots")
    stock["ingestion_time"] = pd.to_datetime(stock["ingestion_time"], utc=True).dt.tz_convert(None)
    stock["known_by_cutoff"] = stock["ingestion_time"] <= _decision_cutoff(stock, cutoff_hour)

    key_columns = ["business_date", "store_id", "product_id"]
    all_keys = stock[key_columns].drop_duplicates()
    known = _latest_by_key(
        stock.loc[stock["known_by_cutoff"]].rename(columns={"on_hand_quantity": "observed_inventory"}),
        ["observed_inventory"],
    )
    late_keys = stock.loc[~stock["known_by_cutoff"], key_columns].drop_duplicates()
    late_keys["late_stock_snapshot"] = True

    stock_daily = all_keys.merge(known, on=key_columns, how="left")
    stock_daily = stock_daily.merge(late_keys, on=key_columns, how="left")
    stock_daily["late_stock_snapshot"] = (
        stock_daily["late_stock_snapshot"].where(stock_daily["late_stock_snapshot"].notna(), False).astype(bool)
    )
    return stock_daily[columns], True


def _aggregate_optional_sources(
    inputs: DailyRetailInputs,
    *,
    cutoff_hour: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    prices = _filter_known_by_cutoff(
        _empty_or_copy(inputs.prices),
        known_at_column="known_at",
        cutoff_hour=cutoff_hour,
    )
    prices = _map_products(prices, inputs.product_master, "prices")
    price_daily = _latest_by_key(prices, ["price"])

    promotions = _filter_known_by_cutoff(
        _empty_or_copy(inputs.promotions),
        known_at_column="known_at",
        cutoff_hour=cutoff_hour,
    )
    if promotions.empty:
        promotion_daily = pd.DataFrame(columns=["business_date", "store_id", "product_id", "promotion"])
    else:
        promotions = _map_products(promotions, inputs.product_master, "promotions")
        promotion_daily = (
            promotions.groupby(["business_date", "store_id", "product_id"], as_index=False)
            .agg(promotion=("promotion", "max"))
        )

    stock_daily, stock_source_present = _stock_daily(inputs, cutoff_hour=cutoff_hour)

    return price_daily, promotion_daily, stock_daily, stock_source_present


def _attach_censoring_contract(daily: pd.DataFrame, *, stock_source_present: bool) -> pd.DataFrame:
    enriched = daily.copy()
    if "observed_inventory" not in enriched.columns:
        enriched["observed_inventory"] = np.nan
    if "late_stock_snapshot" not in enriched.columns:
        enriched["late_stock_snapshot"] = False
    observed_inventory = pd.to_numeric(enriched["observed_inventory"], errors="coerce")
    observed_sales = pd.to_numeric(enriched["observed_sales"], errors="coerce")

    enriched["late_stock_snapshot"] = (
        enriched["late_stock_snapshot"].where(enriched["late_stock_snapshot"].notna(), False).astype(bool)
    )
    enriched["stockout_observed"] = observed_inventory <= 0
    enriched["stockout_observed"] = (
        enriched["stockout_observed"].where(enriched["stockout_observed"].notna(), False).astype(bool)
    )

    enriched["is_censored_demand"] = False
    enriched["censoring_reason"] = "not_censored"
    enriched["stockout_flag"] = False
    if not stock_source_present:
        return _attach_latent_demand_defaults(enriched)

    missing_stock = observed_inventory.isna()
    late_stock = missing_stock & enriched["late_stock_snapshot"]
    zero_stock = observed_inventory <= 0
    insufficient_stock = (observed_inventory > 0) & (observed_inventory <= observed_sales)

    reason_masks = (
        ("late_stock_snapshot", late_stock),
        ("missing_stock_snapshot", missing_stock & ~late_stock),
        ("zero_stock", zero_stock),
        ("insufficient_stock", insufficient_stock),
    )
    for reason, mask in reason_masks:
        enriched.loc[mask, "is_censored_demand"] = True
        enriched.loc[mask, "censoring_reason"] = reason

    enriched["stockout_flag"] = enriched["is_censored_demand"].astype(bool)
    return _attach_latent_demand_defaults(enriched)


def _attach_latent_demand_defaults(frame: pd.DataFrame) -> pd.DataFrame:
    adjusted = frame.copy()
    sales = pd.to_numeric(adjusted["observed_sales"], errors="coerce").astype(float)
    adjusted["latent_demand_estimate"] = sales
    adjusted["latent_demand_lower"] = sales
    adjusted["latent_demand_upper"] = sales
    adjusted["latent_demand_provenance"] = "observed_available_sales"
    adjusted["latent_demand_training_weight"] = 1.0
    censored = adjusted["is_censored_demand"].astype(bool)
    adjusted.loc[censored, "latent_demand_provenance"] = "censored_observed_sales"
    adjusted.loc[censored, "latent_demand_training_weight"] = 0.0
    return adjusted


def build_canonical_daily_demand(
    inputs: DailyRetailInputs,
    *,
    decision_cutoff_hour: int = 6,
) -> pd.DataFrame:
    """Build and validate the canonical daily modelling panel."""
    if not 0 <= decision_cutoff_hour <= 23:
        raise DataContractError("decision_cutoff_hour must be between 0 and 23")

    sales = deduplicate_versioned_events(inputs.sales, "sales")
    daily = _aggregate_sales(sales, inputs.product_master)
    price_daily, promotion_daily, stock_daily, stock_source_present = _aggregate_optional_sources(
        inputs,
        cutoff_hour=decision_cutoff_hour,
    )

    daily = daily.merge(
        price_daily.rename(columns={"business_date": "date"}),
        on=["date", "store_id", "product_id"],
        how="left",
    )
    daily = daily.merge(
        promotion_daily.rename(columns={"business_date": "date"}),
        on=["date", "store_id", "product_id"],
        how="left",
    )
    daily = daily.merge(
        stock_daily.rename(columns={"business_date": "date"}),
        on=["date", "store_id", "product_id"],
        how="left",
    )

    daily["promotion"] = daily["promotion"].where(daily["promotion"].notna(), 0).astype(int)
    daily = _attach_censoring_contract(daily, stock_source_present=stock_source_present)
    daily["shrinkage_rate"] = 0.0
    daily["record_error_std"] = 0.0
    daily["generated_at_utc"] = pd.Timestamp.now(tz=UTC).isoformat()

    result = daily.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)
    validation = validate_daily_demand(result)
    if not validation.is_valid:
        raise DataContractError("; ".join(validation.errors))
    return result


__all__ = [
    "DailyRetailInputs",
    "DataContractError",
    "build_canonical_daily_demand",
    "deduplicate_versioned_events",
]
