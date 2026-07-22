"""Hierarchy-aware fallbacks and cold-start forecasting utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

from perishable_lab.forecasting.quantile import quantile_column

ColdStartState = Literal[
    "mature",
    "unseen_product",
    "unseen_store",
    "unseen_store_product_pair",
    "insufficient_recent_history",
    "structural_change",
]


@dataclass(frozen=True)
class HierarchyConfig:
    """Controls for hierarchy-aware fallback decisions."""

    min_store_product_history: int = 14
    min_parent_history: int = 30
    recent_history_days: int = 28
    prior_strength: float = 20.0


@dataclass(frozen=True)
class ForecastExplanation:
    """Per-row explanation for hierarchy fallback output."""

    store_id: str
    product_id: str
    cold_start_state: ColdStartState
    selected_source: str
    effective_training_sample: int
    calibration_source: str
    confidence_limitations: str
    contributing_levels: tuple[str, ...]


def classify_cold_start_state(
    row: pd.Series,
    history: pd.DataFrame,
    *,
    config: HierarchyConfig | None = None,
) -> ColdStartState:
    """Classify one scored row using only prior history."""
    active_config = config or HierarchyConfig()
    prior = history[pd.to_datetime(history["date"]) < pd.Timestamp(row["date"])]
    store_seen = bool((prior["store_id"] == row["store_id"]).any())
    product_seen = bool((prior["product_id"] == row["product_id"]).any())
    pair_history = prior[
        (prior["store_id"] == row["store_id"]) & (prior["product_id"] == row["product_id"])
    ]
    if bool(row.get("structural_change_flag", False)):
        return "structural_change"
    if not product_seen:
        return "unseen_product"
    if not store_seen:
        return "unseen_store"
    if pair_history.empty:
        return "unseen_store_product_pair"
    recent_cutoff = pd.Timestamp(row["date"]) - pd.Timedelta(days=active_config.recent_history_days)
    recent = pair_history[pd.to_datetime(pair_history["date"]) >= recent_cutoff]
    if int(recent.shape[0]) < active_config.min_store_product_history:
        return "insufficient_recent_history"
    return "mature"


def build_hierarchical_features(
    frame: pd.DataFrame,
    hierarchy: pd.DataFrame,
    *,
    known_at: str | pd.Timestamp,
    source_product_column: str = "product_id",
) -> pd.DataFrame:
    """Join hierarchy attributes using mappings known at the requested cutoff."""
    required = {"product_id", "effective_from", "known_at"}
    missing = sorted(required.difference(hierarchy.columns))
    if missing:
        raise ValueError(f"Hierarchy is missing columns: {missing}")
    left = frame.copy(deep=True)
    left["date"] = pd.to_datetime(left["date"])
    left["_row_id"] = range(len(left))

    known_ts = pd.Timestamp(known_at)
    known_ts = known_ts.tz_localize("UTC") if known_ts.tzinfo is None else known_ts.tz_convert("UTC")
    right = hierarchy.copy(deep=True)
    right["effective_from"] = pd.to_datetime(right["effective_from"]).dt.normalize()
    right["effective_to"] = pd.to_datetime(right["effective_to"]).dt.normalize()
    right["known_at"] = pd.to_datetime(right["known_at"], utc=True)
    right = right[right["known_at"] <= known_ts]

    joined = left.merge(
        right,
        left_on=source_product_column,
        right_on="product_id",
        how="left",
        suffixes=("", "_hierarchy"),
    )
    active = (joined["date"] >= joined["effective_from"]) & (
        joined["effective_to"].isna() | (joined["date"] <= joined["effective_to"])
    )
    joined = joined.loc[active | joined["effective_from"].isna()]
    return (
        joined.sort_values(["_row_id", "known_at", "effective_from"])
        .drop_duplicates("_row_id", keep="last")
        .drop(columns=["_row_id"])
        .reset_index(drop=True)
    )


def empirical_bayes_shrinkage(
    local_value: float,
    parent_value: float,
    local_sample_size: int,
    *,
    prior_strength: float,
) -> float:
    """Shrink a local estimate toward a parent estimate."""
    if local_sample_size < 0:
        raise ValueError("Local sample size cannot be negative")
    if prior_strength < 0.0:
        raise ValueError("Prior strength cannot be negative")
    weight = local_sample_size / max(local_sample_size + prior_strength, 1e-9)
    return float(weight * local_value + (1.0 - weight) * parent_value)


def _monotone_quantiles(values: list[float]) -> list[float]:
    return list(np.maximum.accumulate(np.maximum(values, 0.0)))


def _history_pool(history: pd.DataFrame, row: pd.Series, *, level: str) -> pd.DataFrame:
    prior = history[pd.to_datetime(history["date"]) < pd.Timestamp(row["date"])]
    if level == "store_product":
        return pd.DataFrame(
            prior[
                (prior["store_id"] == row["store_id"])
                & (prior["product_id"] == row["product_id"])
            ]
        )
    if level == "product":
        return pd.DataFrame(prior[prior["product_id"] == row["product_id"]])
    if level == "category" and "category_id" in prior.columns and "category_id" in row.index:
        return pd.DataFrame(prior[prior["category_id"] == row["category_id"]])
    if level == "store" and "store_id" in prior.columns:
        return pd.DataFrame(prior[prior["store_id"] == row["store_id"]])
    return pd.DataFrame(prior)


@dataclass(frozen=True)
class HierarchicalFallbackRouter:
    """Route each scored row to the most specific reliable fallback distribution."""

    quantiles: tuple[float, ...] = (0.05, 0.5, 0.95)
    config: HierarchyConfig = HierarchyConfig()

    def predict_row(self, row: pd.Series, history: pd.DataFrame) -> tuple[dict[str, float], ForecastExplanation]:
        """Predict monotone non-negative quantiles and return an explanation."""
        state = classify_cold_start_state(row, history, config=self.config)
        level_order = ("store_product", "product", "category", "store", "retailer")
        selected_source = "retailer"
        selected_pool = pd.DataFrame()
        for level in level_order:
            pool = _history_pool(history, row, level=level)
            required = (
                self.config.min_store_product_history
                if level == "store_product"
                else self.config.min_parent_history
            )
            if int(pool.shape[0]) >= required:
                selected_source = level
                selected_pool = pool
                break
        if selected_pool.empty:
            selected_pool = _history_pool(history, row, level="retailer")
            selected_source = "retailer"
        if selected_pool.empty:
            raise ValueError("At least one historical row is required for fallback forecasting")

        demand = pd.to_numeric(selected_pool["demand"], errors="coerce").dropna()
        values = _monotone_quantiles([float(demand.quantile(quantile)) for quantile in self.quantiles])
        prediction = {
            quantile_column(quantile): value for quantile, value in zip(self.quantiles, values, strict=True)
        }
        explanation = ForecastExplanation(
            store_id=str(row["store_id"]),
            product_id=str(row["product_id"]),
            cold_start_state=state,
            selected_source=selected_source,
            effective_training_sample=int(selected_pool.shape[0]),
            calibration_source=selected_source
            if int(selected_pool.shape[0]) >= self.config.min_parent_history
            else "global",
            confidence_limitations=_confidence_limitations(state, selected_source),
            contributing_levels=tuple(
                level for level in level_order if not _history_pool(history, row, level=level).empty
            ),
        )
        return prediction, explanation

    def predict(self, scoring_frame: pd.DataFrame, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Predict a batch and return predictions plus explanation artifacts."""
        prediction_rows: list[dict[str, object]] = []
        explanation_rows: list[dict[str, object]] = []
        for _, row in scoring_frame.sort_values(["date", "store_id", "product_id"]).iterrows():
            prediction, explanation = self.predict_row(row, history)
            prediction_rows.append(
                {
                    "date": row["date"],
                    "store_id": row["store_id"],
                    "product_id": row["product_id"],
                    **prediction,
                }
            )
            explanation_rows.append(
                {**asdict(explanation), "contributing_levels": "|".join(explanation.contributing_levels)}
            )
        return pd.DataFrame(prediction_rows), pd.DataFrame(explanation_rows)


def _confidence_limitations(state: ColdStartState, selected_source: str) -> str:
    if state == "mature" and selected_source == "store_product":
        return "store-product history is sufficient"
    if state == "structural_change":
        return "recent item change limits comparability"
    if state.startswith("unseen"):
        return "prediction transferred from broader hierarchy"
    return "recent local history is limited"


def reconcile_bottom_up(
    child_forecasts: pd.DataFrame,
    *,
    group_columns: tuple[str, ...],
    quantile_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Aggregate child forecasts so parent sums equal bottom-up totals."""
    return (
        child_forecasts.groupby(list(group_columns), as_index=False)[list(quantile_columns)]
        .sum()
        .sort_values(list(group_columns), ignore_index=True)
    )


def build_cold_start_evaluation_report(
    predictions: pd.DataFrame,
    *,
    truth_column: str = "demand",
    median_column: str = "q50",
    lower_column: str = "q05",
    upper_column: str = "q95",
) -> pd.DataFrame:
    """Report error and interval metrics by cold-start state."""
    required = {truth_column, median_column, lower_column, upper_column, "cold_start_state"}
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(f"Predictions are missing columns: {missing}")

    rows: list[dict[str, object]] = []
    for state, group in predictions.groupby("cold_start_state", sort=True):
        group_frame = pd.DataFrame(group)
        truth = pd.to_numeric(group_frame[truth_column], errors="coerce")
        median = pd.to_numeric(group_frame[median_column], errors="coerce")
        lower = pd.to_numeric(group_frame[lower_column], errors="coerce")
        upper = pd.to_numeric(group_frame[upper_column], errors="coerce")
        rows.append(
            {
                "cold_start_state": state,
                "rows": int(group_frame.shape[0]),
                "bias": float((median - truth).mean()),
                "mae": float((median - truth).abs().mean()),
                "coverage": float(((truth >= lower) & (truth <= upper)).mean()),
                "mean_width": float((upper - lower).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("cold_start_state", ignore_index=True)
