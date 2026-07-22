"""Split-conformal calibration for central prediction intervals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ConformalIntervalCalibrator:
    """Symmetric additive correction for lower and upper quantile forecasts."""

    lower_column: str
    upper_column: str
    miscoverage: float
    adjustment: float

    @classmethod
    def fit(
        cls,
        target: pd.Series,
        predictions: pd.DataFrame,
        lower_column: str,
        upper_column: str,
        miscoverage: float,
    ) -> ConformalIntervalCalibrator:
        """Estimate a finite-sample conformal adjustment."""
        if not 0.0 < miscoverage < 1.0:
            raise ValueError("Miscoverage must be strictly between zero and one")
        if len(target) != len(predictions):
            raise ValueError("Target and predictions must have equal length")

        y = target.to_numpy(dtype=float)
        lower = predictions[lower_column].to_numpy(dtype=float)
        upper = predictions[upper_column].to_numpy(dtype=float)
        scores = np.maximum(lower - y, y - upper)
        n = len(scores)
        finite_sample_probability = min(1.0, np.ceil((n + 1) * (1.0 - miscoverage)) / n)
        adjustment = float(np.quantile(scores, finite_sample_probability, method="higher"))
        return cls(lower_column, upper_column, miscoverage, max(adjustment, 0.0))

    def transform(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Apply the calibrated interval while preserving non-negative demand."""
        transformed = predictions.copy()
        transformed[self.lower_column] = np.maximum(
            transformed[self.lower_column].to_numpy(dtype=float) - self.adjustment,
            0.0,
        )
        transformed[self.upper_column] = (
            transformed[self.upper_column].to_numpy(dtype=float) + self.adjustment
        )
        return transformed
