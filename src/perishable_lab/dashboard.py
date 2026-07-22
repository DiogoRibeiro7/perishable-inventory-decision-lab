"""Operational dashboard metrics, semantic layer, and demo data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

DashboardView = Literal["portfolio", "customer_success", "data_science", "store_drilldown", "on_call"]
MetricTiming = Literal["leading", "outcome"]


class DashboardMetricError(ValueError):
    """Raised when dashboard inputs or aggregates are inconsistent."""


@dataclass(frozen=True)
class MetricDefinition:
    """Metric dictionary entry with numerator, denominator, timing, and action."""

    name: str
    view: DashboardView
    numerator: str
    denominator: str
    timing: MetricTiming
    threshold: float | None
    uncertainty: str
    action: str
    runbook: str


@dataclass(frozen=True)
class SemanticField:
    """Semantic-layer field exposed to dashboards."""

    name: str
    source: str
    grain: str
    description: str
    freshness_hours: float
    access_level: Literal["portfolio", "store", "restricted"]


@dataclass(frozen=True)
class DashboardMetricRow:
    """Computed dashboard metric with denominator and sample size."""

    metric: str
    value: float
    numerator: float
    denominator: float
    sample_size: int
    timing: MetricTiming
    uncertainty_low: float | None
    uncertainty_high: float | None


def default_metric_dictionary() -> tuple[MetricDefinition, ...]:
    """Return dashboard metrics tied to views and actions."""
    return (
        MetricDefinition("waste_rate", "portfolio", "waste_units", "ordered_units", "outcome", 0.08, "binomial_interval", "open affected stores", "docs/OBSERVABILITY_RUNBOOK.md"),
        MetricDefinition("availability_rate", "portfolio", "fulfilled_units", "demand_units", "outcome", 0.95, "binomial_interval", "inspect harmed segments", "docs/OBSERVABILITY_RUNBOOK.md"),
        MetricDefinition("margin_proxy_per_unit", "portfolio", "margin_proxy", "demand_units", "outcome", None, "bootstrap_or_segment_range", "review product mix", "docs/PERFORMANCE_SCALING.md"),
        MetricDefinition("acceptance_rate", "customer_success", "accepted_count", "recommendation_count", "leading", 0.80, "binomial_interval", "review override reasons", "docs/STORE_DISCOVERY_GUIDE.md"),
        MetricDefinition("forecast_interval_width", "data_science", "forecast_width_sum", "forecast_count", "leading", None, "distribution_summary", "inspect calibration", "docs/MODEL_CARD.md"),
        MetricDefinition("fallback_rate", "data_science", "fallback_count", "recommendation_count", "leading", 0.05, "binomial_interval", "review fallback drivers", "docs/OBSERVABILITY_RUNBOOK.md"),
        MetricDefinition("publication_completeness", "on_call", "published_rows", "expected_rows", "leading", 1.0, "none", "hold publication if incomplete", "docs/PUBLICATION_RUNBOOK.md"),
    )


def semantic_layer_spec() -> tuple[SemanticField, ...]:
    """Return semantic fields used by role-specific dashboard views."""
    return (
        SemanticField("business_date", "fct_dashboard_daily", "store_product_day", "Store operating date", 24.0, "portfolio"),
        SemanticField("store_id", "fct_dashboard_daily", "store_product_day", "Store identifier", 24.0, "store"),
        SemanticField("product_id", "fct_dashboard_daily", "store_product_day", "Product identifier", 24.0, "store"),
        SemanticField("forecast_p05", "fct_dashboard_daily", "store_product_day", "Lower forecast interval", 6.0, "store"),
        SemanticField("forecast_p50", "fct_dashboard_daily", "store_product_day", "Median forecast", 6.0, "store"),
        SemanticField("forecast_p95", "fct_dashboard_daily", "store_product_day", "Upper forecast interval", 6.0, "store"),
        SemanticField("recommended_order_quantity", "fct_dashboard_daily", "store_product_day", "Published or staged recommendation", 6.0, "store"),
        SemanticField("override_reason", "fct_dashboard_daily", "store_product_day", "Captured review reason", 6.0, "restricted"),
        SemanticField("waste_units", "fct_dashboard_daily", "store_product_day", "Recorded waste units", 48.0, "store"),
        SemanticField("fulfilled_units", "fct_dashboard_daily", "store_product_day", "Fulfilled demand units", 48.0, "store"),
        SemanticField("incident_count", "fct_dashboard_daily", "store_product_day", "Operational incident count", 1.0, "portfolio"),
    )


def build_dashboard_demo_data() -> pd.DataFrame:
    """Return screenshot-ready deterministic demo data."""
    rows: list[dict[str, object]] = []
    dates = pd.date_range("2026-01-01", periods=14, freq="D")
    for store_index, store_id in enumerate(["S001", "S002", "S003"]):
        for product_index, product_id in enumerate(["P001", "P002", "P003"]):
            for day_index, date in enumerate(dates):
                demand = 8 + store_index + product_index + day_index % 4
                recommended = demand + (1 if product_index == 0 else 0)
                accepted = 0 if store_id == "S003" and product_id == "P002" and day_index > 7 else 1
                fulfilled = demand - (3 if store_id == "S003" and day_index > 5 else 0)
                waste = 1 if product_id == "P003" and day_index % 5 == 0 else 0
                fallback = 1 if product_id == "P002" and day_index in (3, 10) else 0
                rows.append(
                    {
                        "business_date": date.date().isoformat(),
                        "store_id": store_id,
                        "product_id": product_id,
                        "department": "fresh",
                        "demand_units": demand,
                        "fulfilled_units": fulfilled,
                        "ordered_units": recommended,
                        "waste_units": waste,
                        "margin_proxy": fulfilled * 1.2 - waste * 0.5,
                        "recommendation_count": 1,
                        "accepted_count": accepted,
                        "fallback_count": fallback,
                        "forecast_p05": float(max(0, demand - 3)),
                        "forecast_p50": float(demand),
                        "forecast_p95": float(demand + 5),
                        "forecast_width_sum": 8.0,
                        "forecast_count": 1,
                        "recommended_order_quantity": recommended,
                        "actual_sales": fulfilled,
                        "stock_belief_units": recommended + 2,
                        "pending_order_units": 2,
                        "shelf_life_cohorts": "1d:2|2d:4|3d:6",
                        "override_reason": "" if accepted else "back_room_stock",
                        "supplier_exception_count": 1 if store_id == "S002" and day_index == 9 else 0,
                        "incident_count": 1 if store_id == "S003" and day_index == 10 else 0,
                        "published_rows": 1,
                        "expected_rows": 1,
                        "outcome_available_at": (date + pd.Timedelta(days=2)).isoformat(),
                        "recommendation_explanation": "forecast interval, stock belief, pending order, and case pack",
                    }
                )
    return pd.DataFrame(rows)


def compute_dashboard_metrics(
    frame: pd.DataFrame,
    *,
    group_columns: tuple[str, ...] = (),
    as_of: str | None = None,
    metric_dictionary: tuple[MetricDefinition, ...] | None = None,
) -> pd.DataFrame:
    """Compute dashboard metrics with denominators, samples, and timing."""
    dictionary = metric_dictionary or default_metric_dictionary()
    required = {field for metric in dictionary for field in (metric.numerator, metric.denominator)}
    required.update(group_columns)
    _require_columns(frame, required)
    leading = frame.copy(deep=True)
    if as_of is None or "outcome_available_at" not in frame.columns:
        outcome = leading
    else:
        outcome = leading[pd.to_datetime(leading["outcome_available_at"], utc=True) <= pd.Timestamp(as_of).tz_convert("UTC")]

    metric_rows: list[dict[str, object]] = []
    groups = _groups(leading, group_columns)
    for group_key, leading_group in groups:
        outcome_group = _filter_group(outcome, group_columns, group_key)
        group_values = _group_values(group_columns, group_key)
        for metric in dictionary:
            source = leading_group if metric.timing == "leading" else outcome_group
            numerator = float(pd.to_numeric(source[metric.numerator], errors="coerce").sum()) if not source.empty else 0.0
            denominator = float(pd.to_numeric(source[metric.denominator], errors="coerce").sum()) if not source.empty else 0.0
            value = safe_divide(numerator, denominator)
            uncertainty = _binomial_interval(numerator, denominator) if metric.uncertainty == "binomial_interval" else (None, None)
            metric_rows.append(
                {
                    **group_values,
                    **asdict(
                        DashboardMetricRow(
                            metric=metric.name,
                            value=value,
                            numerator=numerator,
                            denominator=denominator,
                            sample_size=int(source.shape[0]),
                            timing=metric.timing,
                            uncertainty_low=uncertainty[0],
                            uncertainty_high=uncertainty[1],
                        )
                    ),
                }
            )
    return pd.DataFrame(metric_rows)


def harmed_segments(
    metric_frame: pd.DataFrame,
    *,
    metric: str,
    segment_columns: tuple[str, ...],
    threshold: float,
    direction: Literal["above", "below"],
) -> pd.DataFrame:
    """Return segments where aggregate improvement could hide harm."""
    _require_columns(metric_frame, {"metric", "value", "denominator", *segment_columns})
    scoped = metric_frame[metric_frame["metric"] == metric].copy(deep=True)
    if direction == "above":
        harmed = scoped[scoped["value"] > threshold]
    else:
        harmed = scoped[scoped["value"] < threshold]
    return harmed.sort_values([*segment_columns, "metric"], ignore_index=True)


def build_store_drilldown(frame: pd.DataFrame, *, store_id: str, product_id: str) -> pd.DataFrame:
    """Return store-product drill-down rows with recommendation evidence."""
    columns = [
        "business_date",
        "store_id",
        "product_id",
        "demand_units",
        "actual_sales",
        "waste_units",
        "stock_belief_units",
        "pending_order_units",
        "shelf_life_cohorts",
        "forecast_p05",
        "forecast_p50",
        "forecast_p95",
        "recommended_order_quantity",
        "recommendation_explanation",
        "override_reason",
    ]
    _require_columns(frame, set(columns))
    scoped = frame[(frame["store_id"] == store_id) & (frame["product_id"] == product_id)]
    return scoped[columns].sort_values("business_date", ignore_index=True)


def apply_dashboard_filters(
    frame: pd.DataFrame,
    *,
    stores: tuple[str, ...] = (),
    products: tuple[str, ...] = (),
    departments: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Apply dashboard filters consistently."""
    filtered = frame.copy(deep=True)
    if stores:
        filtered = filtered[filtered["store_id"].isin(stores)]
    if products:
        filtered = filtered[filtered["product_id"].isin(products)]
    if departments and "department" in filtered.columns:
        filtered = filtered[filtered["department"].isin(departments)]
    return filtered.reset_index(drop=True)


def apply_row_access(frame: pd.DataFrame, *, allowed_store_ids: tuple[str, ...]) -> pd.DataFrame:
    """Limit store-level rows to allowed stores."""
    if not allowed_store_ids:
        raise DashboardMetricError("allowed_store_ids cannot be empty")
    _require_columns(frame, {"store_id"})
    return frame[frame["store_id"].isin(allowed_store_ids)].reset_index(drop=True)


def assert_aggregate_matches_drilldown(
    aggregate: pd.DataFrame,
    drilldown: pd.DataFrame,
    *,
    metric: str,
) -> None:
    """Verify aggregate numerator and denominator equal drill-down totals."""
    agg_row = aggregate[aggregate["metric"] == metric]
    drill_rows = drilldown[drilldown["metric"] == metric]
    if agg_row.shape[0] != 1:
        raise DashboardMetricError("aggregate must contain exactly one metric row")
    if not np.isclose(float(agg_row["numerator"].iloc[0]), float(drill_rows["numerator"].sum())):
        raise DashboardMetricError("aggregate numerator does not match drill-down")
    if not np.isclose(float(agg_row["denominator"].iloc[0]), float(drill_rows["denominator"].sum())):
        raise DashboardMetricError("aggregate denominator does not match drill-down")


def alert_drilldown_links(alert_ids: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Map alerts to dashboard drill-downs and runbooks."""
    return {
        alert_id: {
            "drilldown": f"/dashboards/on-call?alert_id={alert_id}",
            "runbook": "docs/OBSERVABILITY_RUNBOOK.md",
        }
        for alert_id in alert_ids
    }


def safe_divide(numerator: float, denominator: float) -> float:
    """Return zero for empty denominators while preserving explicit denominator fields."""
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _binomial_interval(numerator: float, denominator: float) -> tuple[float | None, float | None]:
    if denominator <= 0:
        return (None, None)
    value = safe_divide(numerator, denominator)
    width = 1.96 * np.sqrt(max(value * (1.0 - value), 0.0) / denominator)
    return (max(0.0, value - width), min(1.0, value + width))


def _groups(frame: pd.DataFrame, group_columns: tuple[str, ...]) -> list[tuple[tuple[object, ...], pd.DataFrame]]:
    if not group_columns:
        return [((), frame)]
    return [
        ((keys if isinstance(keys, tuple) else (keys,)), group)
        for keys, group in frame.groupby(list(group_columns), sort=True, dropna=False)
    ]


def _filter_group(frame: pd.DataFrame, group_columns: tuple[str, ...], group_key: tuple[object, ...]) -> pd.DataFrame:
    if not group_columns:
        return frame
    mask = pd.Series(True, index=frame.index)
    for column, value in zip(group_columns, group_key, strict=True):
        mask &= frame[column].astype(str).eq(str(value))
    return frame[mask]


def _group_values(group_columns: tuple[str, ...], group_key: tuple[object, ...]) -> dict[str, object]:
    return {column: value for column, value in zip(group_columns, group_key, strict=True)}


def _require_columns(frame: pd.DataFrame, columns: set[str]) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise DashboardMetricError(f"Missing dashboard columns: {missing}")
