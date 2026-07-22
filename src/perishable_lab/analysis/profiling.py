"""Deterministic profiling for store-product-day retail data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from perishable_lab import __version__

REQUIRED_COLUMNS = ("date", "store_id", "product_id", "demand")
BUSINESS_KEY = ("date", "store_id", "product_id")


@dataclass(frozen=True)
class ProfileConfig:
    """Controls for exploratory summaries and quality rules."""

    min_segment_size: int = 20
    stock_jump_multiplier: float = 5.0

    def __post_init__(self) -> None:
        if self.min_segment_size < 1:
            raise ValueError("Minimum segment size must be positive")
        if self.stock_jump_multiplier <= 0.0:
            raise ValueError("Stock jump multiplier must be positive")


@dataclass(frozen=True)
class QualityIssue:
    """Single data-quality rule result."""

    rule_id: str
    severity: str
    table: str
    scope: str
    rows: int
    message: str


@dataclass(frozen=True)
class ChartMetadata:
    """Metadata contract for rendered or tabular profile views."""

    name: str
    operational_question: str
    source_table: str
    filters: str
    date_range: str
    code_version: str
    output_path: str


@dataclass(frozen=True)
class ProfileResult:
    """Complete deterministic profiling output."""

    global_summary: pd.DataFrame
    segment_summary: pd.DataFrame
    quality_issues: tuple[QualityIssue, ...]
    data_quality_rules: pd.DataFrame
    chart_metadata: tuple[ChartMetadata, ...]
    modelling_implications: tuple[str, ...]

    def quality_issues_frame(self) -> pd.DataFrame:
        """Return quality issues as a stable data frame."""
        columns = ["rule_id", "severity", "table", "scope", "rows", "message"]
        if not self.quality_issues:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame([asdict(issue) for issue in self.quality_issues], columns=columns).sort_values(
            ["severity", "rule_id", "scope"], ignore_index=True
        )

    def chart_metadata_frame(self) -> pd.DataFrame:
        """Return chart metadata as a stable data frame."""
        return pd.DataFrame([asdict(item) for item in self.chart_metadata]).sort_values(
            ["name"], ignore_index=True
        )


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    prepared = frame.copy(deep=True)
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["demand"] = pd.to_numeric(prepared["demand"], errors="coerce")
    prepared["weekday"] = prepared["date"].dt.day_name()
    prepared["season"] = prepared["date"].dt.month.map(_season)
    return prepared


def _season(month: float) -> str:
    month_int = int(month)
    if month_int in (12, 1, 2):
        return "winter"
    if month_int in (3, 4, 5):
        return "spring"
    if month_int in (6, 7, 8):
        return "summer"
    return "autumn"


def _date_range(prepared: pd.DataFrame) -> str:
    valid_dates = prepared["date"].dropna()
    if valid_dates.empty:
        return "unknown"
    start = valid_dates.min().strftime("%Y-%m-%d")
    end = valid_dates.max().strftime("%Y-%m-%d")
    return f"{start} to {end}"


def _robust_demand_stats(demand: pd.Series) -> dict[str, float | int]:
    clean = pd.to_numeric(demand, errors="coerce").dropna()
    if clean.empty:
        return {
            "rows": 0,
            "total_demand": 0.0,
            "median_demand": 0.0,
            "demand_iqr": 0.0,
            "zero_rate": 0.0,
            "variance_to_mean": 0.0,
            "outlier_count": 0,
        }

    q1 = float(clean.quantile(0.25))
    median = float(clean.median())
    q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    upper_fence = q3 + 3.0 * iqr
    if iqr == 0.0:
        upper_fence = median + max(10.0, 3.0 * median)
    mean = float(clean.mean())
    variance = float(clean.var(ddof=0))
    return {
        "rows": int(clean.shape[0]),
        "total_demand": float(clean.sum()),
        "median_demand": median,
        "demand_iqr": float(iqr),
        "zero_rate": float((clean == 0).mean()),
        "variance_to_mean": float(variance / max(mean, 1e-9)),
        "outlier_count": int((clean > upper_fence).sum()),
    }


def _global_summary(prepared: pd.DataFrame) -> pd.DataFrame:
    stats = _robust_demand_stats(prepared["demand"])
    records: list[dict[str, str | float | int]] = [
        {"metric": "rows", "value": int(prepared.shape[0])},
        {"metric": "stores", "value": int(prepared["store_id"].nunique())},
        {"metric": "products", "value": int(prepared["product_id"].nunique())},
        {"metric": "dates", "value": int(prepared["date"].nunique())},
        {"metric": "date_range", "value": _date_range(prepared)},
        {"metric": "missing_required_values", "value": int(prepared[list(REQUIRED_COLUMNS)].isna().sum().sum())},
    ]
    records.extend({"metric": key, "value": value} for key, value in stats.items())

    for column in ("category", "category_id", "supplier", "supplier_id"):
        if column in prepared.columns:
            records.append({"metric": f"{column}s", "value": int(prepared[column].nunique())})

    return pd.DataFrame(records).sort_values("metric", ignore_index=True)


def _segment_summary(prepared: pd.DataFrame, config: ProfileConfig) -> pd.DataFrame:
    segment_columns = [
        column
        for column in (
            "store_id",
            "product_id",
            "category",
            "category_id",
            "supplier",
            "supplier_id",
            "weekday",
            "season",
            "promotion",
        )
        if column in prepared.columns
    ]
    records: list[dict[str, object]] = []
    for column in segment_columns:
        for value, group in prepared.groupby(column, dropna=False, sort=True):
            group_frame = pd.DataFrame(group)
            suppressed = int(group_frame.shape[0]) < config.min_segment_size
            stats = _robust_demand_stats(group_frame["demand"])
            records.append(
                {
                    "segment_type": column,
                    "segment_value": str(value),
                    "rows": int(group_frame.shape[0]),
                    "distinct_dates": int(group_frame["date"].nunique()),
                    "suppressed": suppressed,
                    "total_demand": None if suppressed else stats["total_demand"],
                    "median_demand": None if suppressed else stats["median_demand"],
                    "demand_iqr": None if suppressed else stats["demand_iqr"],
                    "zero_rate": None if suppressed else stats["zero_rate"],
                    "variance_to_mean": None if suppressed else stats["variance_to_mean"],
                    "outlier_count": None if suppressed else stats["outlier_count"],
                }
            )
    return pd.DataFrame(records).sort_values(["segment_type", "segment_value"], ignore_index=True)


def _duplicate_issues(prepared: pd.DataFrame, source_table: str) -> list[QualityIssue]:
    duplicates = prepared.duplicated(list(BUSINESS_KEY), keep=False)
    if not bool(duplicates.any()):
        return []
    return [
        QualityIssue(
            rule_id="duplicate_business_key",
            severity="blocking",
            table=source_table,
            scope="date_store_product",
            rows=int(duplicates.sum()),
            message="Duplicate date-store-product keys must be resolved before training or scoring.",
        )
    ]


def _missing_day_issues(prepared: pd.DataFrame, source_table: str) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for keys, group in prepared.groupby(["store_id", "product_id"], sort=True):
        group_frame = pd.DataFrame(group)
        dates = group_frame["date"].dropna().drop_duplicates().sort_values()
        if dates.empty:
            continue
        expected = pd.date_range(dates.min(), dates.max(), freq="D")
        missing_count = len(expected.difference(pd.DatetimeIndex(dates)))
        if missing_count > 0:
            store_id, product_id = keys
            issues.append(
                QualityIssue(
                    rule_id="missing_store_product_days",
                    severity="warning",
                    table=source_table,
                    scope=f"store_id={store_id},product_id={product_id}",
                    rows=missing_count,
                    message="Missing business dates can bias lag features and rolling demand summaries.",
                )
            )
    return issues


def _stock_issues(prepared: pd.DataFrame, source_table: str, config: ProfileConfig) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for column in ("observed_inventory", "physical_inventory"):
        if column not in prepared.columns:
            continue
        stock = pd.to_numeric(prepared[column], errors="coerce")
        negative = stock < 0
        if bool(negative.any()):
            issues.append(
                QualityIssue(
                    rule_id=f"negative_{column}",
                    severity="blocking",
                    table=source_table,
                    scope=column,
                    rows=int(negative.sum()),
                    message="Negative inventory must be corrected upstream or blocked.",
                )
            )

        jump_count = 0
        for _, group in prepared.assign(_stock=stock).groupby(["store_id", "product_id"], sort=True):
            group_frame = pd.DataFrame(group).sort_values("date")
            demand_median = float(pd.to_numeric(group_frame["demand"], errors="coerce").median())
            threshold = max(20.0, config.stock_jump_multiplier * max(demand_median, 1.0))
            jump_count += int((group_frame["_stock"].diff().abs() > threshold).sum())
        if jump_count:
            issues.append(
                QualityIssue(
                    rule_id=f"impossible_{column}_jump",
                    severity="warning",
                    table=source_table,
                    scope=column,
                    rows=jump_count,
                    message="Large stock transitions need delivery, waste, adjustment, or counting evidence.",
                )
            )
    return issues


def _optional_domain_issues(prepared: pd.DataFrame, source_table: str) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    demand = pd.to_numeric(prepared["demand"], errors="coerce")
    negative_demand = demand < 0
    if bool(negative_demand.any()):
        issues.append(
            QualityIssue(
                rule_id="negative_demand",
                severity="blocking",
                table=source_table,
                scope="demand",
                rows=int(negative_demand.sum()),
                message="Negative demand is invalid for the forecasting target.",
            )
        )

    if "observed_inventory" in prepared.columns:
        stock = pd.to_numeric(prepared["observed_inventory"], errors="coerce")
        censored = (stock <= 0) & (demand <= 1)
        if bool(censored.any()):
            issues.append(
                QualityIssue(
                    rule_id="stockout_censoring_evidence",
                    severity="warning",
                    table=source_table,
                    scope="observed_inventory",
                    rows=int(censored.sum()),
                    message="Low sales with no recorded stock is evidence that sales may be censored demand.",
                )
            )

    if "shelf_life_days" in prepared.columns:
        shelf_life = pd.to_numeric(prepared["shelf_life_days"], errors="coerce")
        invalid = shelf_life <= 0
        if bool(invalid.any()):
            issues.append(
                QualityIssue(
                    rule_id="invalid_shelf_life",
                    severity="blocking",
                    table=source_table,
                    scope="shelf_life_days",
                    rows=int(invalid.sum()),
                    message="Shelf life must be positive for perishable simulation.",
                )
            )

    if "lead_time_days" in prepared.columns:
        lead_time = pd.to_numeric(prepared["lead_time_days"], errors="coerce")
        invalid = lead_time < 0
        if bool(invalid.any()):
            issues.append(
                QualityIssue(
                    rule_id="invalid_lead_time",
                    severity="blocking",
                    table=source_table,
                    scope="lead_time_days",
                    rows=int(invalid.sum()),
                    message="Negative supplier lead time is not operationally valid.",
                )
            )

    if {"promotion", "discount_depth"}.issubset(prepared.columns):
        promotion = pd.to_numeric(prepared["promotion"], errors="coerce").fillna(0) > 0
        discount = pd.to_numeric(prepared["discount_depth"], errors="coerce").fillna(0)
        no_discount = promotion & (discount <= 0)
        if bool(no_discount.any()):
            issues.append(
                QualityIssue(
                    rule_id="promotion_without_discount_depth",
                    severity="informational",
                    table=source_table,
                    scope="promotion",
                    rows=int(no_discount.sum()),
                    message="Promotion flags without discount depth limit price-effect interpretation.",
                )
            )

    if "timezone" in prepared.columns and int(prepared["timezone"].nunique(dropna=True)) > 1:
        issues.append(
            QualityIssue(
                rule_id="mixed_timezones",
                severity="warning",
                table=source_table,
                scope="timezone",
                rows=int(prepared["timezone"].nunique(dropna=True)),
                message="Mixed time zones must be normalized before cutoff-sensitive feature generation.",
            )
        )

    if {"source_product_id", "product_id"}.issubset(prepared.columns):
        source_to_canonical = prepared.groupby("source_product_id")["product_id"].nunique()
        canonical_to_source = prepared.groupby("product_id")["source_product_id"].nunique()
        churn_rows = int((source_to_canonical > 1).sum() + (canonical_to_source > 1).sum())
        if churn_rows:
            issues.append(
                QualityIssue(
                    rule_id="product_identity_churn",
                    severity="warning",
                    table=source_table,
                    scope="source_product_id,product_id",
                    rows=churn_rows,
                    message="Many-to-one or one-to-many product mappings require effective-dated lineage.",
                )
            )

    return issues


def _data_quality_rules() -> pd.DataFrame:
    records = [
        ("duplicate_business_key", "blocking", "Duplicate date-store-product keys."),
        ("negative_demand", "blocking", "Demand target is below zero."),
        ("negative_observed_inventory", "blocking", "Recorded inventory is below zero."),
        ("negative_physical_inventory", "blocking", "Physical inventory proxy is below zero."),
        ("invalid_shelf_life", "blocking", "Shelf life is not positive."),
        ("invalid_lead_time", "blocking", "Supplier lead time is negative."),
        ("missing_store_product_days", "warning", "Panel has missing dates."),
        ("impossible_observed_inventory_jump", "warning", "Recorded stock jump lacks support."),
        ("impossible_physical_inventory_jump", "warning", "Physical stock jump lacks support."),
        ("stockout_censoring_evidence", "warning", "Observed sales may be censored by availability."),
        ("mixed_timezones", "warning", "Multiple time zones appear in one analysis frame."),
        ("product_identity_churn", "warning", "Product mappings are not stable."),
        ("promotion_without_discount_depth", "informational", "Promotion lacks discount depth."),
    ]
    return pd.DataFrame(records, columns=["rule_id", "severity", "description"])


def _chart_metadata(source_table: str, prepared: pd.DataFrame) -> tuple[ChartMetadata, ...]:
    date_range = _date_range(prepared)
    return (
        ChartMetadata(
            name="coverage_by_segment",
            operational_question="Which stores, products, weekdays, seasons, categories, and suppliers have enough observations to support modelling?",
            source_table=source_table,
            filters="none",
            date_range=date_range,
            code_version=__version__,
            output_path="segment_summary.csv",
        ),
        ChartMetadata(
            name="demand_distribution",
            operational_question="Where are demand tails, zero inflation, and outliers large enough to change loss and fallback choices?",
            source_table=source_table,
            filters="none",
            date_range=date_range,
            code_version=__version__,
            output_path="global_summary.csv",
        ),
        ChartMetadata(
            name="quality_severity_table",
            operational_question="Which records must be blocked before training or scoring?",
            source_table=source_table,
            filters="none",
            date_range=date_range,
            code_version=__version__,
            output_path="quality_issues.csv",
        ),
    )


def _modelling_implications(result: ProfileResult) -> tuple[str, ...]:
    issue_ids = {issue.rule_id for issue in result.quality_issues}
    implications = [
        "Use robust statistics and quantile losses when variance-to-mean demand ratios indicate overdispersion.",
        "Suppress tiny segments in charts and model-selection decisions until they meet the configured sample threshold.",
    ]
    if "stockout_censoring_evidence" in issue_ids:
        implications.append(
            "Treat low sales with no stock as censored demand before fitting forecasting targets."
        )
    if "missing_store_product_days" in issue_ids:
        implications.append(
            "Add explicit missing-day indicators or block incomplete series before lag and rolling features."
        )
    if "promotion_without_discount_depth" in issue_ids:
        implications.append(
            "Model promotion flags separately from price effects when discount depth is unavailable."
        )
    if "product_identity_churn" in issue_ids:
        implications.append(
            "Resolve product identity before learning categorical effects or evaluating cold starts."
        )
    if any(issue.severity == "blocking" for issue in result.quality_issues):
        implications.append("Block training and scoring until blocking data-quality issues are resolved.")
    return tuple(implications)


def profile_daily_frame(
    frame: pd.DataFrame,
    *,
    source_table: str = "daily_demand",
    config: ProfileConfig | None = None,
) -> ProfileResult:
    """Profile a store-product-day frame without modifying source values."""
    active_config = config or ProfileConfig()
    prepared = _prepare_frame(frame)
    issues = (
        _duplicate_issues(prepared, source_table)
        + _missing_day_issues(prepared, source_table)
        + _stock_issues(prepared, source_table, active_config)
        + _optional_domain_issues(prepared, source_table)
    )
    result = ProfileResult(
        global_summary=_global_summary(prepared),
        segment_summary=_segment_summary(prepared, active_config),
        quality_issues=tuple(issues),
        data_quality_rules=_data_quality_rules(),
        chart_metadata=_chart_metadata(source_table, prepared),
        modelling_implications=(),
    )
    return ProfileResult(
        global_summary=result.global_summary,
        segment_summary=result.segment_summary,
        quality_issues=result.quality_issues,
        data_quality_rules=result.data_quality_rules,
        chart_metadata=result.chart_metadata,
        modelling_implications=_modelling_implications(result),
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def _markdown_report(result: ProfileResult) -> str:
    issue_counts = result.quality_issues_frame()
    if issue_counts.empty:
        severity_lines = "- No data-quality issues detected."
    else:
        counts = issue_counts.groupby("severity").size().sort_index()
        severity_lines = "\n".join(f"- {severity}: {count}" for severity, count in counts.items())

    implication_lines = "\n".join(f"- {item}" for item in result.modelling_implications)
    return "\n".join(
        [
            "# Data Profile Report",
            "",
            "## Summary Tables",
            "",
            "- [Global summary](global_summary.csv)",
            "- [Segment summary](segment_summary.csv)",
            "- [Quality issues](quality_issues.csv)",
            "- [Quality rules](data_quality_rules.csv)",
            "- [Chart metadata](chart_metadata.csv)",
            "",
            "## Data-Quality Severity",
            "",
            severity_lines,
            "",
            "## Modelling Implications",
            "",
            implication_lines,
            "",
        ]
    )


def write_profile_report(
    frame: pd.DataFrame,
    output_dir: Path,
    *,
    source_table: str = "daily_demand",
    config: ProfileConfig | None = None,
) -> ProfileResult:
    """Write deterministic profile tables and a Markdown report."""
    result = profile_daily_frame(frame, source_table=source_table, config=config)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "global_summary.csv", result.global_summary)
    _write_csv(output_dir / "segment_summary.csv", result.segment_summary)
    _write_csv(output_dir / "quality_issues.csv", result.quality_issues_frame())
    _write_csv(output_dir / "data_quality_rules.csv", result.data_quality_rules)
    _write_csv(output_dir / "chart_metadata.csv", result.chart_metadata_frame())
    (output_dir / "profile_report.md").write_text(_markdown_report(result), encoding="utf-8")
    return result
