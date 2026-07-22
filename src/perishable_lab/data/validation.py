"""Input-data contract checks."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = {
    "date",
    "store_id",
    "product_id",
    "demand",
    "price",
    "promotion",
    "shelf_life_days",
    "lead_time_days",
    "unit_cost",
    "unit_margin",
    "waste_cost",
    "shrinkage_rate",
    "record_error_std",
}


@dataclass(frozen=True)
class ValidationResult:
    """Structured result for data-contract validation."""

    is_valid: bool
    errors: tuple[str, ...]


def validate_daily_demand(frame: pd.DataFrame) -> ValidationResult:
    """Validate the minimum data contract required by the pipeline."""
    errors: list[str] = []
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return ValidationResult(False, tuple(errors))

    if frame.empty:
        errors.append("Input data is empty")
    if frame[["date", "store_id", "product_id"]].duplicated().any():
        errors.append("Duplicate store-product-date keys detected")
    if (frame["demand"] < 0).any():
        errors.append("Demand cannot be negative")
    if (frame["shelf_life_days"] < 1).any():
        errors.append("Shelf life must be at least one day")
    if (frame["lead_time_days"] < 0).any():
        errors.append("Lead time cannot be negative")
    if frame[sorted(REQUIRED_COLUMNS)].isna().any().any():
        errors.append("Required columns contain missing values")

    return ValidationResult(not errors, tuple(errors))
