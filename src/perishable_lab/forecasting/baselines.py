"""Forecast baselines for fallback and benchmark scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.forecasting.quantile import quantile_column


def _empirical_quantiles(
    values: NDArray[np.float64],
    quantiles: tuple[float, ...],
) -> NDArray[np.float64]:
    if len(values) == 0:
        values = np.array([0.0], dtype=np.float64)
    estimated = np.quantile(np.maximum(values, 0.0), quantiles).astype(np.float64)
    return np.maximum.accumulate(estimated)


def sba_intermittent_forecast(demand: pd.Series, *, alpha: float = 0.1) -> float:
    """Return an SBA-adjusted Croston-style point forecast for intermittent demand."""
    if not 0.0 < alpha <= 1.0:
        raise ValueError("Alpha must be in the interval (0, 1]")

    values = demand.to_numpy(dtype=np.float64)
    positive_indices = np.flatnonzero(values > 0.0)
    if len(positive_indices) == 0:
        return 0.0

    demand_level = float(values[positive_indices[0]])
    interval_level = float(positive_indices[0] + 1)
    last_positive = int(positive_indices[0])
    for index in positive_indices[1:]:
        interval = float(index - last_positive)
        demand_level += alpha * (float(values[index]) - demand_level)
        interval_level += alpha * (interval - interval_level)
        last_positive = int(index)

    if interval_level <= 0.0:
        return max(demand_level, 0.0)
    return float(max((1.0 - alpha / 2.0) * demand_level / interval_level, 0.0))


@dataclass
class SeasonalNaiveQuantileForecaster:
    """Empirical same-weekday quantile fallback with hierarchical backoff."""

    quantiles: tuple[float, ...] = (0.05, 0.1, 0.5, 0.9, 0.95)
    group_columns: tuple[str, ...] = ("store_id", "product_id")
    date_column: str = "date"
    target_column: str = "demand"
    min_history: int = 3
    global_values_: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    group_values_: dict[tuple[object, ...], NDArray[np.float64]] = field(default_factory=dict)
    seasonal_values_: dict[tuple[object, ...], NDArray[np.float64]] = field(default_factory=dict)

    def fit(self, frame: pd.DataFrame) -> SeasonalNaiveQuantileForecaster:
        """Store empirical demand histories used by fallback predictions."""
        required = {self.date_column, self.target_column, *self.group_columns}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Training frame is missing columns: {missing}")
        if frame.empty:
            raise ValueError("Training frame cannot be empty")

        prepared = frame.copy()
        prepared[self.date_column] = pd.to_datetime(prepared[self.date_column])
        prepared["_day_of_week"] = prepared[self.date_column].dt.dayofweek
        self.global_values_ = prepared[self.target_column].to_numpy(dtype=np.float64)
        self.group_values_.clear()
        self.seasonal_values_.clear()

        for group_key, group in prepared.groupby(list(self.group_columns), sort=False):
            key = group_key if isinstance(group_key, tuple) else (group_key,)
            self.group_values_[key] = group[self.target_column].to_numpy(dtype=np.float64)
            for day_of_week, seasonal_group in group.groupby("_day_of_week", sort=False):
                self.seasonal_values_[(*key, int(str(day_of_week)))] = seasonal_group[
                    self.target_column
                ].to_numpy(dtype=np.float64)
        return self

    def _values_for_row(self, row: pd.Series) -> NDArray[np.float64]:
        key = tuple(row[column] for column in self.group_columns)
        day_of_week = int(pd.Timestamp(row[self.date_column]).dayofweek)
        seasonal = self.seasonal_values_.get((*key, day_of_week))
        if seasonal is not None and len(seasonal) >= self.min_history:
            return seasonal
        group_values = self.group_values_.get(key)
        if group_values is not None and len(group_values) >= self.min_history:
            return group_values
        return self.global_values_

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predict non-negative monotone empirical quantiles for each row."""
        if len(self.global_values_) == 0:
            raise RuntimeError("The fallback forecaster must be fitted before prediction")
        required = {self.date_column, *self.group_columns}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Prediction frame is missing columns: {missing}")

        rows = [
            _empirical_quantiles(self._values_for_row(row), self.quantiles)
            for _, row in frame.iterrows()
        ]
        matrix = np.vstack(rows).astype(np.float64)
        return pd.DataFrame(
            matrix,
            columns=[quantile_column(q) for q in self.quantiles],
            index=frame.index,
        )


__all__ = ["SeasonalNaiveQuantileForecaster", "sba_intermittent_forecast"]
