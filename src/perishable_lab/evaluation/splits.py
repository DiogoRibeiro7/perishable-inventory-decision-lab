"""Time-aware data splits."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TemporalSplit:
    """Boolean masks for train, calibration, and test periods."""

    train: pd.Series
    calibration: pd.Series
    test: pd.Series
    train_end: pd.Timestamp
    calibration_end: pd.Timestamp


def three_way_temporal_split(
    dates: pd.Series,
    train_fraction: float = 0.60,
    calibration_fraction: float = 0.20,
) -> TemporalSplit:
    """Split unique dates into contiguous train, calibration, and test windows."""
    if train_fraction <= 0.0 or calibration_fraction <= 0.0:
        raise ValueError("Fractions must be positive")
    if train_fraction + calibration_fraction >= 1.0:
        raise ValueError("Train plus calibration fraction must be below one")

    unique_dates = pd.Series(pd.to_datetime(dates).unique()).sort_values().reset_index(drop=True)
    if len(unique_dates) < 30:
        raise ValueError("At least 30 unique dates are required")

    train_idx = max(1, int(len(unique_dates) * train_fraction)) - 1
    calibration_idx = max(train_idx + 1, int(len(unique_dates) * (train_fraction + calibration_fraction))) - 1
    train_end = pd.Timestamp(unique_dates.iloc[train_idx])
    calibration_end = pd.Timestamp(unique_dates.iloc[calibration_idx])
    parsed = pd.to_datetime(dates)
    return TemporalSplit(
        train=parsed <= train_end,
        calibration=(parsed > train_end) & (parsed <= calibration_end),
        test=parsed > calibration_end,
        train_end=train_end,
        calibration_end=calibration_end,
    )


def rolling_origin_cutoffs(
    dates: pd.Series,
    *,
    minimum_train_days: int = 90,
    horizon_days: int = 14,
    step_days: int = 14,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return rolling-origin train cutoffs and evaluation end dates."""
    unique_dates = pd.Series(pd.to_datetime(dates).unique()).sort_values().reset_index(drop=True)
    if minimum_train_days < 28 or horizon_days < 1 or step_days < 1:
        raise ValueError("Invalid rolling-origin parameters")
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    origin_idx = minimum_train_days - 1
    while origin_idx + horizon_days < len(unique_dates):
        train_end = pd.Timestamp(unique_dates.iloc[origin_idx])
        test_end = pd.Timestamp(unique_dates.iloc[origin_idx + horizon_days])
        windows.append((train_end, test_end))
        origin_idx += step_days
    return windows
