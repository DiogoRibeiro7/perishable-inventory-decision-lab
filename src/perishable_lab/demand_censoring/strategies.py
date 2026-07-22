"""Strategies for separating observed sales from latent demand estimates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
import pandas as pd


class DemandCensoringError(ValueError):
    """Raised when source rows cannot support censoring correction."""


@dataclass(frozen=True)
class CensoringDiagnostics:
    """Summary diagnostics for a censoring strategy run."""

    method: str
    rows: int
    censored_rows: int
    fallback_rows: int
    iterations: int = 1
    converged: bool = True
    mean_absolute_change: float = 0.0


@dataclass(frozen=True)
class CensoringResult:
    """Latent-demand frame plus deterministic run diagnostics."""

    frame: pd.DataFrame
    diagnostics: CensoringDiagnostics


class DemandCensoringStrategy(Protocol):
    """Common interface for latent-demand estimation strategies."""

    @property
    def name(self) -> str:
        """Stable strategy identifier."""
        ...

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        """Return a frame with separate observed, estimated, bound, and provenance columns."""
        ...


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy(deep=True)
    if "observed_sales" not in prepared.columns:
        if "demand" not in prepared.columns:
            raise DemandCensoringError("Frame must include observed_sales or demand")
        prepared["observed_sales"] = prepared["demand"]
    required = {"date", "store_id", "product_id", "observed_sales"}
    missing = sorted(required.difference(prepared.columns))
    if missing:
        raise DemandCensoringError(f"Missing required columns: {missing}")

    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["observed_sales"] = pd.to_numeric(prepared["observed_sales"], errors="coerce")
    if bool(prepared["date"].isna().any()):
        raise DemandCensoringError("Date values must be parseable")
    if bool((prepared["observed_sales"] < 0).any()):
        raise DemandCensoringError("Observed sales cannot be negative")

    for column in ("observed_inventory", "physical_stock_belief", "opening_inventory"):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
            if bool((prepared[column] < 0).any()):
                raise DemandCensoringError(f"{column} cannot be negative")

    prepared = prepared.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    prepared["is_censored_demand"] = _censoring_mask(prepared)
    if "censoring_reason" not in prepared.columns:
        prepared["censoring_reason"] = "not_censored"
    prepared.loc[~prepared["is_censored_demand"], "censoring_reason"] = "not_censored"
    return prepared


def _censoring_mask(frame: pd.DataFrame) -> pd.Series:
    censored = pd.Series(False, index=frame.index)
    if "is_censored_demand" in frame.columns:
        censored = censored | frame["is_censored_demand"].fillna(False).astype(bool)
    if "stockout_flag" in frame.columns:
        censored = censored | frame["stockout_flag"].fillna(False).astype(bool)
    if "observed_inventory" in frame.columns:
        stock = pd.to_numeric(frame["observed_inventory"], errors="coerce")
        censored = censored | (stock <= 0)
    if "physical_stock_belief" in frame.columns:
        belief = pd.to_numeric(frame["physical_stock_belief"], errors="coerce")
        censored = censored | (belief <= 0)
    return censored


def _empty_adjusted_frame(prepared: pd.DataFrame) -> pd.DataFrame:
    adjusted = prepared.copy(deep=True)
    sales = pd.to_numeric(adjusted["observed_sales"], errors="coerce").astype(float)
    adjusted["latent_demand_estimate"] = sales
    adjusted["latent_demand_lower"] = sales
    adjusted["latent_demand_upper"] = sales
    adjusted["latent_demand_provenance"] = "observed_available_sales"
    adjusted["latent_demand_training_weight"] = 1.0
    return adjusted


def _historical_pool(frame: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    prior = frame[frame["date"] < row["date"]]
    prior = prior[~prior["is_censored_demand"]]
    if "promotion" in frame.columns:
        same_promotion = prior[prior["promotion"] == row["promotion"]]
        if not same_promotion.empty:
            prior = same_promotion

    same_store_product = prior[
        (prior["store_id"] == row["store_id"]) & (prior["product_id"] == row["product_id"])
    ]
    if not same_store_product.empty:
        return pd.DataFrame(same_store_product)

    same_product = prior[prior["product_id"] == row["product_id"]]
    if not same_product.empty:
        return pd.DataFrame(same_product)

    return pd.DataFrame(prior)


def _historical_quantile(
    frame: pd.DataFrame,
    row: pd.Series,
    *,
    quantile: float,
    min_history: int,
) -> tuple[float, bool]:
    pool = _historical_pool(frame, row)
    sales = pd.to_numeric(pool["observed_sales"], errors="coerce").dropna()
    fallback = int(sales.shape[0]) < min_history
    if sales.empty:
        return float(row["observed_sales"]), True
    return float(sales.quantile(quantile)), fallback


def _diagnostics(
    method: str,
    frame: pd.DataFrame,
    *,
    fallback_rows: int,
    iterations: int = 1,
    converged: bool = True,
    mean_absolute_change: float = 0.0,
) -> CensoringDiagnostics:
    return CensoringDiagnostics(
        method=method,
        rows=int(frame.shape[0]),
        censored_rows=int(frame["is_censored_demand"].sum()),
        fallback_rows=fallback_rows,
        iterations=iterations,
        converged=converged,
        mean_absolute_change=mean_absolute_change,
    )


@dataclass(frozen=True)
class ConservativeExcludeStrategy:
    """Keep observed sales, flag censored rows, and exclude them from training."""

    name: str = "flag_exclude"

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        prepared = _prepare_frame(frame)
        adjusted = _empty_adjusted_frame(prepared)
        censored = adjusted["is_censored_demand"].astype(bool)
        adjusted.loc[censored, "latent_demand_provenance"] = "censored_excluded"
        adjusted.loc[censored, "latent_demand_training_weight"] = 0.0
        return CensoringResult(
            frame=adjusted,
            diagnostics=_diagnostics(self.name, adjusted, fallback_rows=0),
        )


@dataclass(frozen=True)
class ComparablePeriodImputer:
    """Impute censored rows from earlier comparable non-stockout periods."""

    min_history: int = 2
    quantile: float = 0.5
    name: str = "comparable_period"

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        prepared = _prepare_frame(frame)
        adjusted = _empty_adjusted_frame(prepared)
        fallback_rows = 0

        for index, row in adjusted[adjusted["is_censored_demand"]].iterrows():
            estimate, fallback = _historical_quantile(
                adjusted, row, quantile=self.quantile, min_history=self.min_history
            )
            observed = float(row["observed_sales"])
            adjusted.loc[index, "latent_demand_estimate"] = max(observed, estimate)
            adjusted.loc[index, "latent_demand_lower"] = observed
            adjusted.loc[index, "latent_demand_upper"] = max(observed, estimate)
            adjusted.loc[index, "latent_demand_provenance"] = (
                "fallback_observed_sales" if fallback else "historical_comparable_sales"
            )
            adjusted.loc[index, "latent_demand_training_weight"] = 1.0
            fallback_rows += int(fallback)

        return CensoringResult(
            frame=adjusted,
            diagnostics=_diagnostics(self.name, adjusted, fallback_rows=fallback_rows),
        )


@dataclass(frozen=True)
class TobitStyleCountStrategy:
    """Approximate censored non-negative counts with a conservative upper tail estimate."""

    min_history: int = 2
    tail_quantile: float = 0.75
    name: str = "count_likelihood_approx"

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        prepared = _prepare_frame(frame)
        adjusted = _empty_adjusted_frame(prepared)
        fallback_rows = 0

        for index, row in adjusted[adjusted["is_censored_demand"]].iterrows():
            tail, fallback = _historical_quantile(
                adjusted, row, quantile=self.tail_quantile, min_history=self.min_history
            )
            observed = float(row["observed_sales"])
            estimate = max(observed, 0.5 * observed + 0.5 * tail)
            adjusted.loc[index, "latent_demand_estimate"] = estimate
            adjusted.loc[index, "latent_demand_lower"] = observed
            adjusted.loc[index, "latent_demand_upper"] = max(observed, tail)
            adjusted.loc[index, "latent_demand_provenance"] = (
                "fallback_tobit_style_bound" if fallback else "tobit_style_count_approximation"
            )
            adjusted.loc[index, "latent_demand_training_weight"] = 1.0
            fallback_rows += int(fallback)

        return CensoringResult(
            frame=adjusted,
            diagnostics=_diagnostics(self.name, adjusted, fallback_rows=fallback_rows),
        )


@dataclass(frozen=True)
class IterativeImputeRefitStrategy:
    """Iteratively impute censored rows from historical estimates until stable."""

    min_history: int = 2
    max_iterations: int = 10
    tolerance: float = 1e-3
    name: str = "iterative_impute_refit"

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        prepared = _prepare_frame(frame)
        adjusted = _empty_adjusted_frame(prepared)
        censored_index = adjusted.index[adjusted["is_censored_demand"]].tolist()
        fallback_rows = 0
        previous = pd.to_numeric(adjusted["latent_demand_estimate"], errors="coerce").astype(float)
        mean_absolute_change = 0.0
        converged = False
        iterations = 0

        for iteration in range(1, self.max_iterations + 1):
            iterations = iteration
            fallback_rows = 0
            history_frame = adjusted.copy(deep=True)
            history_frame["observed_sales"] = history_frame["latent_demand_estimate"]
            for index in censored_index:
                row = adjusted.loc[index]
                estimate, fallback = _historical_quantile(
                    history_frame,
                    row,
                    quantile=0.5,
                    min_history=self.min_history,
                )
                observed = float(row["observed_sales"])
                adjusted.loc[index, "latent_demand_estimate"] = max(observed, estimate)
                adjusted.loc[index, "latent_demand_lower"] = observed
                adjusted.loc[index, "latent_demand_upper"] = max(observed, estimate)
                adjusted.loc[index, "latent_demand_provenance"] = (
                    "fallback_iterative_observed_sales" if fallback else "iterative_history_estimate"
                )
                fallback_rows += int(fallback)

            current = pd.to_numeric(adjusted["latent_demand_estimate"], errors="coerce").astype(float)
            mean_absolute_change = float(np.abs(current - previous).mean())
            if mean_absolute_change <= self.tolerance:
                converged = True
                break
            previous = current.copy()

        return CensoringResult(
            frame=adjusted,
            diagnostics=_diagnostics(
                self.name,
                adjusted,
                fallback_rows=fallback_rows,
                iterations=iterations,
                converged=converged,
                mean_absolute_change=mean_absolute_change,
            ),
        )


@dataclass(frozen=True)
class DemandBoundsStrategy:
    """Emit lower and upper latent-demand bounds when point imputation is not justified."""

    min_history: int = 2
    upper_quantile: float = 0.9
    name: str = "bounds"

    def adjust(self, frame: pd.DataFrame) -> CensoringResult:
        prepared = _prepare_frame(frame)
        adjusted = _empty_adjusted_frame(prepared)
        fallback_rows = 0

        for index, row in adjusted[adjusted["is_censored_demand"]].iterrows():
            upper, fallback = _historical_quantile(
                adjusted, row, quantile=self.upper_quantile, min_history=self.min_history
            )
            observed = float(row["observed_sales"])
            adjusted.loc[index, "latent_demand_estimate"] = observed
            adjusted.loc[index, "latent_demand_lower"] = observed
            adjusted.loc[index, "latent_demand_upper"] = max(observed, upper)
            adjusted.loc[index, "latent_demand_provenance"] = (
                "fallback_bounds_observed_sales" if fallback else "historical_demand_bounds"
            )
            adjusted.loc[index, "latent_demand_training_weight"] = 0.0
            fallback_rows += int(fallback)

        return CensoringResult(
            frame=adjusted,
            diagnostics=_diagnostics(self.name, adjusted, fallback_rows=fallback_rows),
        )


def select_censoring_strategy(
    method: Literal[
        "flag_exclude",
        "comparable_period",
        "count_likelihood_approx",
        "iterative_impute_refit",
        "bounds",
    ],
    *,
    min_history: int = 2,
    max_iterations: int = 10,
    tolerance: float = 1e-3,
) -> DemandCensoringStrategy:
    """Create a censoring strategy from configuration values."""
    if method == "flag_exclude":
        return ConservativeExcludeStrategy()
    if method == "comparable_period":
        return ComparablePeriodImputer(min_history=min_history)
    if method == "count_likelihood_approx":
        return TobitStyleCountStrategy(min_history=min_history)
    if method == "iterative_impute_refit":
        return IterativeImputeRefitStrategy(
            min_history=min_history,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    if method == "bounds":
        return DemandBoundsStrategy(min_history=min_history)
    raise ValueError(f"Unsupported censoring method: {method}")


def build_censoring_diagnostic_report(
    result: CensoringResult,
    *,
    segment_columns: tuple[str, ...] = ("store_id", "product_id"),
    true_demand_column: str | None = None,
) -> pd.DataFrame:
    """Summarise censoring severity, estimation error, and interval coverage by segment."""
    frame = result.frame.copy(deep=True)
    records: list[dict[str, object]] = []
    for column in segment_columns:
        if column not in frame.columns:
            continue
        for value, group in frame.groupby(column, sort=True):
            group_frame = pd.DataFrame(group)
            observed = pd.to_numeric(group_frame["observed_sales"], errors="coerce")
            estimate = pd.to_numeric(group_frame["latent_demand_estimate"], errors="coerce")
            record: dict[str, object] = {
                "segment_type": column,
                "segment_value": str(value),
                "rows": int(group_frame.shape[0]),
                "censored_rows": int(group_frame["is_censored_demand"].sum()),
                "censoring_rate": float(group_frame["is_censored_demand"].mean()),
                "mean_observed_sales": float(observed.mean()),
                "mean_latent_demand_estimate": float(estimate.mean()),
                "mean_uplift": float((estimate - observed).mean()),
            }
            if true_demand_column is not None and true_demand_column in group_frame.columns:
                truth = pd.to_numeric(group_frame[true_demand_column], errors="coerce")
                lower = pd.to_numeric(group_frame["latent_demand_lower"], errors="coerce")
                upper = pd.to_numeric(group_frame["latent_demand_upper"], errors="coerce")
                record["bias"] = float((estimate - truth).mean())
                record["mae"] = float((estimate - truth).abs().mean())
                record["interval_coverage"] = float(((truth >= lower) & (truth <= upper)).mean())
            records.append(record)
    return pd.DataFrame(records).sort_values(["segment_type", "segment_value"], ignore_index=True)
