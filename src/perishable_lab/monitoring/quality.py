"""Data and model health reporting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

NUMERIC_HEALTH_COLUMNS = [
    "demand",
    "price",
    "shelf_life_days",
    "lead_time_days",
    "shrinkage_rate",
]


def build_monitoring_report(
    frame: pd.DataFrame,
    forecast_metrics: dict[str, Any],
    *,
    minimum_coverage: float,
    maximum_missing_rate: float,
) -> dict[str, Any]:
    """Create a serialisable monitoring report with explicit alert status."""
    missing_rate = float(frame[NUMERIC_HEALTH_COLUMNS].isna().mean().max())
    duplicate_rate = float(
        frame[["date", "store_id", "product_id"]].duplicated().mean()
    )
    demand_p99 = float(np.quantile(frame["demand"].to_numpy(dtype=float), 0.99))
    coverage = float(forecast_metrics["empirical_coverage"])

    alerts: list[str] = []
    if missing_rate > maximum_missing_rate:
        alerts.append("missing_rate_exceeded")
    if duplicate_rate > 0.0:
        alerts.append("duplicate_keys_detected")
    if coverage < minimum_coverage:
        alerts.append("forecast_undercoverage")

    return {
        "status": "alert" if alerts else "healthy",
        "alerts": alerts,
        "data": {
            "rows": len(frame),
            "maximum_missing_rate": missing_rate,
            "duplicate_key_rate": duplicate_rate,
            "demand_p99": demand_p99,
        },
        "forecast": {
            "empirical_coverage": coverage,
            "mean_interval_width": float(forecast_metrics["mean_interval_width"]),
            "approximate_crps": float(forecast_metrics["approximate_crps"]),
        },
    }
