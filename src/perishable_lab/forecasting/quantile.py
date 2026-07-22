"""Quantile gradient-boosting model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


@dataclass
class QuantileForecaster:
    """Fit one gradient-boosting model per requested quantile."""

    quantiles: tuple[float, ...] = (0.05, 0.1, 0.5, 0.9, 0.95)
    max_iter: int = 120
    learning_rate: float = 0.08
    max_leaf_nodes: int = 24
    min_samples_leaf: int = 20
    random_state: int = 42
    models: dict[float, Pipeline] = field(default_factory=dict, init=False)
    columns_: tuple[str, ...] | None = field(default=None, init=False)

    def fit(self, features: pd.DataFrame, target: pd.Series) -> QuantileForecaster:
        """Fit all quantile models."""
        if features.empty:
            raise ValueError("Features cannot be empty")
        if len(features) != len(target):
            raise ValueError("Features and target must have equal length")

        self.columns_ = tuple(features.columns)
        self.models.clear()
        for quantile in self.quantiles:
            regressor = GradientBoostingRegressor(
                loss="quantile",
                alpha=quantile,
                n_estimators=self.max_iter,
                learning_rate=self.learning_rate,
                max_leaf_nodes=self.max_leaf_nodes,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
            )
            pipeline = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="median")),
                    ("regressor", regressor),
                ]
            )
            pipeline.fit(features, target)
            self.models[quantile] = pipeline
        return self

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """Predict non-negative, monotonically ordered quantiles."""
        if self.columns_ is None or not self.models:
            raise RuntimeError("The forecaster must be fitted before prediction")
        missing = set(self.columns_).difference(features.columns)
        if missing:
            raise ValueError(f"Prediction features are missing columns: {sorted(missing)}")

        matrix = np.column_stack(
            [self.models[q].predict(features.loc[:, self.columns_]) for q in self.quantiles]
        )
        matrix = np.maximum(matrix, 0.0)
        matrix = np.maximum.accumulate(matrix, axis=1)
        columns = [quantile_column(q) for q in self.quantiles]
        return pd.DataFrame(matrix, columns=columns, index=features.index)


def quantile_column(quantile: float) -> str:
    """Convert a probability to a stable column name."""
    return f"q{round(quantile * 100):02d}"


def interpolate_quantile(
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
    probability: float,
) -> NDArray[np.float64]:
    """Linearly interpolate row-wise predictions at an arbitrary probability."""
    if not 0.0 < probability < 1.0:
        raise ValueError("Probability must be strictly between zero and one")
    values = predictions[[quantile_column(q) for q in quantiles]].to_numpy(dtype=float)
    result = np.empty(len(predictions), dtype=float)
    for row_idx, row in enumerate(values):
        result[row_idx] = np.interp(probability, quantiles, row)
    return result


def interpolate_rowwise_quantiles(
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
    probabilities: NDArray[np.floating[Any]],
) -> NDArray[np.float64]:
    """Interpolate each forecast row at its own requested probability."""
    if len(predictions) != len(probabilities):
        raise ValueError("Predictions and probabilities must have equal length")
    if np.any((probabilities <= 0.0) | (probabilities >= 1.0)):
        raise ValueError("Probabilities must be strictly between zero and one")
    values = predictions[[quantile_column(q) for q in quantiles]].to_numpy(dtype=float)
    clipped = np.clip(probabilities, quantiles[0], quantiles[-1])
    result = np.empty(len(predictions), dtype=float)
    for row_idx, row in enumerate(values):
        result[row_idx] = np.interp(clipped[row_idx], quantiles, row)
    return result
