"""Leakage-safe feature engineering for daily demand forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

IDENTIFIER_COLUMNS = ["date", "store_id", "product_id"]
TARGET_COLUMN = "demand"
NON_FEATURE_COLUMNS = {
    *IDENTIFIER_COLUMNS,
    TARGET_COLUMN,
    "unit_cost",
    "unit_margin",
    "waste_cost",
    "observed_sales",
    "source_product_ids",
    "observed_inventory",
    "stockout_observed",
    "stockout_flag",
    "late_stock_snapshot",
    "is_censored_demand",
    "censoring_reason",
    "latent_demand_estimate",
    "latent_demand_lower",
    "latent_demand_upper",
    "latent_demand_provenance",
    "latent_demand_training_weight",
}


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create lagged and calendar features using only information available at prediction time.

    The function assumes that a next-day forecast is produced after the current day's demand
    has closed. Every rolling statistic is shifted by one day to avoid target leakage.
    """
    ordered = frame.sort_values(["store_id", "product_id", "date"]).copy()
    grouped = ordered.groupby(["store_id", "product_id"], sort=False)[TARGET_COLUMN]

    for lag in (1, 7, 14, 28):
        ordered[f"demand_lag_{lag}"] = grouped.shift(lag)

    shifted = grouped.shift(1)
    ordered["demand_mean_7"] = (
        shifted.groupby([ordered["store_id"], ordered["product_id"]])
        .rolling(7, min_periods=3)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )
    ordered["demand_mean_28"] = (
        shifted.groupby([ordered["store_id"], ordered["product_id"]])
        .rolling(28, min_periods=7)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )
    ordered["demand_std_7"] = (
        shifted.groupby([ordered["store_id"], ordered["product_id"]])
        .rolling(7, min_periods=3)
        .std()
        .reset_index(level=[0, 1], drop=True)
    )

    date = pd.to_datetime(ordered["date"])
    day_of_week = date.dt.dayofweek.astype(float)
    day_of_year = date.dt.dayofyear.astype(float)
    ordered["dow_sin"] = np.sin(2.0 * np.pi * day_of_week / 7.0)
    ordered["dow_cos"] = np.cos(2.0 * np.pi * day_of_week / 7.0)
    ordered["year_sin"] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    ordered["year_cos"] = np.cos(2.0 * np.pi * day_of_year / 365.25)

    ordered["store_code"] = pd.Categorical(ordered["store_id"]).codes
    ordered["product_code"] = pd.Categorical(ordered["product_id"]).codes
    return ordered.dropna().reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Return model feature names in deterministic order."""
    return sorted(
        column
        for column in frame.columns
        if column not in NON_FEATURE_COLUMNS
        and (is_numeric_dtype(frame[column]) or is_bool_dtype(frame[column]))
    )
