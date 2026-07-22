"""Decision-time-correct price, promotion, calendar, and event features."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EventFeatureConfig:
    """Controls for event feature construction."""

    decision_cutoff_hour: int = 6
    pre_event_days: int = 7
    post_event_days: int = 7

    def __post_init__(self) -> None:
        if not 0 <= self.decision_cutoff_hour <= 23:
            raise ValueError("Decision cutoff hour must be between 0 and 23")
        if self.pre_event_days < 0 or self.post_event_days < 0:
            raise ValueError("Event windows cannot be negative")


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _prepare_base(frame: pd.DataFrame, config: EventFeatureConfig) -> pd.DataFrame:
    prepared = frame.copy(deep=True)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared["_row_id"] = range(len(prepared))
    prepared["_decision_cutoff"] = prepared["date"] + pd.Timedelta(hours=config.decision_cutoff_hour)
    return prepared


def _latest_known_event(
    base: pd.DataFrame,
    events: pd.DataFrame,
    *,
    config: EventFeatureConfig,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame({"_row_id": base["_row_id"]})
    required = {"date", "store_id", "product_id", "known_at"}
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"Event table is missing columns: {missing}")

    prepared = events.copy(deep=True)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared["known_at"] = pd.to_datetime(prepared["known_at"], utc=True).dt.tz_convert(None)
    if "event_start" in prepared.columns:
        prepared["event_start"] = pd.to_datetime(prepared["event_start"]).dt.normalize()
    else:
        prepared["event_start"] = prepared["date"]
    if "event_end" in prepared.columns:
        prepared["event_end"] = pd.to_datetime(prepared["event_end"]).dt.normalize()
    else:
        prepared["event_end"] = prepared["date"]

    joined = base[["_row_id", "date", "store_id", "product_id", "_decision_cutoff"]].merge(
        prepared,
        on=["store_id", "product_id"],
        how="left",
        suffixes=("", "_event_record"),
    )
    known = joined["known_at"].isna() | (joined["known_at"] <= joined["_decision_cutoff"])
    in_window = (
        joined["event_start"].isna()
        | (
            (joined["date"] >= joined["event_start"] - pd.Timedelta(days=config.pre_event_days))
            & (joined["date"] <= joined["event_end"] + pd.Timedelta(days=config.post_event_days))
        )
    )
    joined = joined.loc[known & in_window]
    if joined.empty:
        return pd.DataFrame({"_row_id": base["_row_id"]})
    return (
        joined.sort_values(["_row_id", "known_at", "event_start"])
        .drop_duplicates("_row_id", keep="last")
        .drop(columns=["date", "date_event_record", "store_id", "product_id", "_decision_cutoff"])
        .reset_index(drop=True)
    )


def _latest_known_calendar(
    base: pd.DataFrame,
    calendar: pd.DataFrame | None,
) -> pd.DataFrame:
    if calendar is None or calendar.empty:
        return pd.DataFrame({"_row_id": base["_row_id"]})
    required = {"date", "known_at"}
    missing = sorted(required.difference(calendar.columns))
    if missing:
        raise ValueError(f"Calendar table is missing columns: {missing}")

    prepared = calendar.copy(deep=True)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared["known_at"] = pd.to_datetime(prepared["known_at"], utc=True).dt.tz_convert(None)
    join_keys = ["date"]
    if "store_id" in prepared.columns:
        join_keys.append("store_id")
    joined = base[["_row_id", "date", "store_id", "_decision_cutoff"]].merge(
        prepared,
        on=join_keys,
        how="left",
        suffixes=("", "_calendar"),
    )
    known = joined["known_at"].isna() | (joined["known_at"] <= joined["_decision_cutoff"])
    joined = joined.loc[known]
    if joined.empty:
        return pd.DataFrame({"_row_id": base["_row_id"]})
    drop_columns = ["date", "_decision_cutoff"]
    if "store_id_calendar" in joined.columns:
        drop_columns.append("store_id_calendar")
    return (
        joined.sort_values(["_row_id", "known_at"])
        .drop_duplicates("_row_id", keep="last")
        .drop(columns=[column for column in drop_columns if column in joined.columns])
        .reset_index(drop=True)
    )


def _event_window(row: pd.Series, config: EventFeatureConfig) -> str:
    if not bool(row.get("promotion_known", False)) or bool(row.get("cancelled_promotion", False)):
        return "normal"
    date = pd.Timestamp(row["date"])
    start = pd.Timestamp(row.get("event_start", row["date"]))
    end = pd.Timestamp(row.get("event_end", row["date"]))
    if start <= date <= end:
        return "active_promotion"
    if start - pd.Timedelta(days=config.pre_event_days) <= date < start:
        return "pre_promotion"
    if end < date <= end + pd.Timedelta(days=config.post_event_days):
        return "post_promotion"
    return "normal"


def build_event_features(
    frame: pd.DataFrame,
    events: pd.DataFrame,
    *,
    calendar: pd.DataFrame | None = None,
    config: EventFeatureConfig | None = None,
) -> pd.DataFrame:
    """Build as-of-safe commercial-event features without repairing source values."""
    active_config = config or EventFeatureConfig()
    base = _prepare_base(frame, active_config)
    event_features = _latest_known_event(base, events, config=active_config)
    calendar_features = _latest_known_calendar(base, calendar)

    featured = base.merge(event_features, on="_row_id", how="left").merge(
        calendar_features,
        on="_row_id",
        how="left",
        suffixes=("", "_calendar"),
    )
    date = pd.to_datetime(featured["date"])
    featured["weekday"] = date.dt.dayofweek
    featured["season"] = date.dt.month.map(lambda month: _season(int(month)))
    featured["promotion_known"] = featured["known_at"].notna() if "known_at" in featured.columns else False
    featured["planned_promotion"] = _column_or_default(featured, "planned_promotion", 0).fillna(0).astype(int)
    featured["published_promotion"] = _column_or_default(featured, "published_promotion", 0).fillna(0).astype(int)
    featured["executed_promotion"] = _column_or_default(featured, "executed_promotion", 0).fillna(0).astype(int)
    featured["promotion_type"] = _column_or_default(featured, "promotion_type", "unknown").fillna("unknown")
    featured["promotion_status"] = _column_or_default(featured, "promotion_status", "unknown").fillna("unknown")
    featured["cancelled_promotion"] = featured["promotion_status"].eq("cancelled")
    featured["regular_price"] = pd.to_numeric(
        _column_or_default(featured, "regular_price", pd.NA), errors="coerce"
    )
    featured["planned_price"] = pd.to_numeric(
        _column_or_default(featured, "planned_price", featured["regular_price"]), errors="coerce"
    )
    featured["discount_depth"] = (
        (featured["regular_price"] - featured["planned_price"]) / featured["regular_price"].clip(lower=1e-9)
    ).fillna(0.0)
    featured["event_start"] = pd.to_datetime(
        _column_or_default(featured, "event_start", featured["date"])
    ).fillna(featured["date"])
    featured["event_end"] = pd.to_datetime(
        _column_or_default(featured, "event_end", featured["date"])
    ).fillna(featured["date"])
    featured["promotion_duration_days"] = (
        (featured["event_end"] - featured["event_start"]).dt.days.clip(lower=0) + 1
    )
    featured["event_window"] = featured.apply(lambda row: _event_window(row, active_config), axis=1)
    featured["public_holiday"] = _bool_column(featured, "public_holiday")
    featured["school_holiday"] = _bool_column(featured, "school_holiday")
    featured["payday"] = _bool_column(featured, "payday")
    featured["store_closed"] = _bool_column(featured, "store_closed")
    if "baseline_velocity" in featured.columns:
        featured["promotion_x_baseline_velocity"] = (
            featured["planned_promotion"] * pd.to_numeric(featured["baseline_velocity"], errors="coerce")
        ).fillna(0.0)
    if "shelf_life_days" in featured.columns:
        featured["discount_x_shelf_life"] = (
            featured["discount_depth"] * pd.to_numeric(featured["shelf_life_days"], errors="coerce")
        ).fillna(0.0)
    return featured.drop(columns=["_row_id", "_decision_cutoff"])


def _column_or_default(frame: pd.DataFrame, column: str, default: object) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)


def _bool_column(frame: pd.DataFrame, column: str) -> pd.Series:
    values = _column_or_default(frame, column, False)
    return values.where(values.notna(), False).astype(bool)


def build_event_window_diagnostics(
    frame: pd.DataFrame,
    *,
    demand_column: str = "demand",
) -> pd.DataFrame:
    """Summarise demand and uplift uncertainty by event window."""
    required = {"event_window", demand_column}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Frame is missing columns: {missing}")
    normal = frame.loc[frame["event_window"] == "normal", demand_column]
    baseline = float(pd.to_numeric(normal, errors="coerce").median()) if not normal.empty else 0.0
    rows: list[dict[str, object]] = []
    for window, group in frame.groupby("event_window", sort=True):
        demand = pd.to_numeric(group[demand_column], errors="coerce").dropna()
        std_error = float(demand.std(ddof=0) / max(len(demand) ** 0.5, 1.0)) if not demand.empty else 0.0
        median = float(demand.median()) if not demand.empty else 0.0
        rows.append(
            {
                "event_window": window,
                "rows": int(group.shape[0]),
                "median_demand": median,
                "uplift_vs_normal_median": median - baseline,
                "uplift_uncertainty_low": median - baseline - 1.96 * std_error,
                "uplift_uncertainty_high": median - baseline + 1.96 * std_error,
            }
        )
    return pd.DataFrame(rows).sort_values("event_window", ignore_index=True)


def promotion_segment_report(
    frame: pd.DataFrame,
    *,
    demand_column: str = "demand",
    median_column: str = "q50",
    lower_column: str = "q05",
    upper_column: str = "q95",
) -> pd.DataFrame:
    """Report calibration and underforecast frequency by commercial-event segment."""
    required = {"event_window", demand_column, median_column, lower_column, upper_column}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Frame is missing columns: {missing}")
    rows: list[dict[str, object]] = []
    for window, group in frame.groupby("event_window", sort=True):
        demand = pd.to_numeric(group[demand_column], errors="coerce")
        median = pd.to_numeric(group[median_column], errors="coerce")
        lower = pd.to_numeric(group[lower_column], errors="coerce")
        upper = pd.to_numeric(group[upper_column], errors="coerce")
        rows.append(
            {
                "event_window": window,
                "rows": int(group.shape[0]),
                "underforecast_rate": float((demand > median).mean()),
                "coverage": float(((demand >= lower) & (demand <= upper)).mean()),
                "mean_width": float((upper - lower).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("event_window", ignore_index=True)


def causal_caution_text() -> str:
    """Return the standard caution for predictive promotion features."""
    return (
        "Promotion features can improve prediction, but predictive uplift is not causal "
        "incrementality. Causal claims require a separate design that handles confounding, "
        "selection into promotion, cannibalisation, forward buying, substitution, and overlap."
    )
