"""Metrics for distributional forecasts."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.forecasting.quantile import quantile_column


def pinball_loss(
    y_true: NDArray[np.float64],
    y_pred: NDArray[np.float64],
    quantile: float,
) -> float:
    """Return mean quantile loss."""
    error = y_true - y_pred
    return float(np.mean(np.maximum(quantile * error, (quantile - 1.0) * error)))


def evaluate_quantile_forecast(
    target: pd.Series,
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
) -> dict[str, Any]:
    """Compute proper scores and interval diagnostics."""
    y = target.to_numpy(dtype=float)
    losses: dict[str, float] = {}
    for quantile in quantiles:
        column = quantile_column(quantile)
        losses[column] = pinball_loss(y, predictions[column].to_numpy(dtype=float), quantile)

    lower_q, upper_q = quantiles[0], quantiles[-1]
    lower = predictions[quantile_column(lower_q)].to_numpy(dtype=float)
    upper = predictions[quantile_column(upper_q)].to_numpy(dtype=float)
    coverage = float(np.mean((y >= lower) & (y <= upper)))
    width = float(np.mean(upper - lower))
    alpha = lower_q + (1.0 - upper_q)
    below = np.maximum(lower - y, 0.0)
    above = np.maximum(y - upper, 0.0)
    interval_score = float(np.mean((upper - lower) + (2.0 / alpha) * (below + above)))
    approximate_crps = float(2.0 * np.mean(list(losses.values())))

    return {
        "pinball_loss": losses,
        "empirical_coverage": coverage,
        "mean_interval_width": width,
        "weighted_interval_score": interval_score,
        "approximate_crps": approximate_crps,
        "rows": len(target),
    }
