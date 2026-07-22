"""Lead-time demand utilities for quantile forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.forecasting.quantile import quantile_column


def horizon_quantile_column(horizon_days: int, quantile: float) -> str:
    """Return a stable cumulative-horizon quantile column name."""
    if horizon_days < 1:
        raise ValueError("Horizon must be at least one day")
    return f"h{horizon_days}_{quantile_column(quantile)}"


def lead_time_horizons(
    frame: pd.DataFrame,
    *,
    lead_time_column: str = "lead_time_days",
    review_period_days: int = 1,
) -> NDArray[np.int64]:
    """Compute row-level protection horizons from lead time plus review period."""
    if review_period_days < 1:
        raise ValueError("Review period must be at least one day")
    if lead_time_column not in frame.columns:
        raise ValueError(f"Missing lead-time column: {lead_time_column}")
    lead_time: NDArray[np.int64] = frame[lead_time_column].to_numpy(dtype=np.int64)
    horizons = np.maximum(1, lead_time + review_period_days).astype(np.int64)
    return horizons


def cumulative_quantile_forecast(
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
    horizons: NDArray[np.integer],
) -> pd.DataFrame:
    """Approximate cumulative lead-time demand from one-day quantile forecasts.

    This baseline assumes each protected day has the same marginal demand
    distribution as the scored row. It is deliberately simple and conservative:
    the output is finite, non-negative, and projected back into monotone order.
    """
    if len(predictions) != len(horizons):
        raise ValueError("Predictions and horizons must have equal length")
    if np.any(horizons < 1):
        raise ValueError("All horizons must be at least one day")

    values = predictions[[quantile_column(q) for q in quantiles]].to_numpy(dtype=np.float64)
    cumulative = np.maximum(values * horizons.reshape(-1, 1), 0.0)
    cumulative = np.maximum.accumulate(cumulative, axis=1)
    columns = [f"lead_time_{quantile_column(q)}" for q in quantiles]
    return pd.DataFrame(cumulative, columns=columns, index=predictions.index)


__all__ = ["cumulative_quantile_forecast", "horizon_quantile_column", "lead_time_horizons"]
