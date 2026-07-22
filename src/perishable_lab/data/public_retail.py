"""Public retail dataset adapters and benchmark helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from perishable_lab.evaluation.splits import rolling_origin_cutoffs
from perishable_lab.features import build_features, feature_columns
from perishable_lab.forecasting.baselines import (
    SeasonalNaiveQuantileForecaster,
    sba_intermittent_forecast,
)
from perishable_lab.forecasting.conformal import ConformalIntervalCalibrator
from perishable_lab.forecasting.metrics import evaluate_quantile_forecast
from perishable_lab.forecasting.quantile import QuantileForecaster

PublicDatasetName = Literal["m5"]

M5_REQUIRED_FILES: tuple[str, ...] = (
    "calendar.csv",
    "sales_train_validation.csv",
    "sell_prices.csv",
)
M5_LEAKAGE_PATTERNS: tuple[str, ...] = (
    "sales_train_evaluation.csv",
    "sample_submission.csv",
    "d_1914",
)


@dataclass(frozen=True)
class DatasetCandidate:
    """Dataset selection notes for public benchmark documentation."""

    name: str
    source_url: str
    access: str
    methodological_fit: str
    missing_operational_fields: tuple[str, ...]
    leakage_notes: tuple[str, ...]
    selected: bool


@dataclass(frozen=True)
class M5AdapterConfig:
    """Controls for converting M5 CSV files to the repository schema."""

    raw_dir: Path
    max_series: int = 8
    first_day: int = 1
    last_day: int | None = None
    seed: int = 42
    expected_checksums: dict[str, str] | None = None


@dataclass(frozen=True)
class PublicBenchmarkConfig:
    """Controls for the public retail benchmark."""

    max_series: int = 8
    minimum_train_days: int = 56
    horizon_days: int = 14
    step_days: int = 14
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    seed: int = 42


def public_dataset_candidates() -> tuple[DatasetCandidate, ...]:
    """Return the dataset choice matrix used by the public benchmark."""
    return (
        DatasetCandidate(
            name="M5 Forecasting - Accuracy",
            source_url="https://www.kaggle.com/competitions/m5-forecasting-accuracy",
            access="Kaggle competition download after accepting competition terms",
            methodological_fit="Daily item-store unit sales, prices, calendar events, and hierarchy; closest fit for demand forecasting.",
            missing_operational_fields=("on-hand inventory", "waste", "expiry", "supplier lead time", "stockout flags"),
            leakage_notes=("evaluation sales and sample submissions must not be used for training",),
            selected=True,
        ),
        DatasetCandidate(
            name="Corporacion Favorita Grocery Sales Forecasting",
            source_url="https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting",
            access="Kaggle competition download after accepting competition terms",
            methodological_fit="Grocery scope with transactions, items, stores, promotions, oil, and holidays.",
            missing_operational_fields=("on-hand inventory", "waste", "expiry", "supplier lead time"),
            leakage_notes=("test-period transaction aggregates and late promotion knowledge require care",),
            selected=False,
        ),
        DatasetCandidate(
            name="Rossmann Store Sales",
            source_url="https://www.kaggle.com/competitions/rossmann-store-sales",
            access="Kaggle competition download after accepting competition terms",
            methodological_fit="Store-level sales forecast with promotion and store attributes, but no item grain.",
            missing_operational_fields=("item demand", "on-hand inventory", "waste", "expiry", "supplier lead time"),
            leakage_notes=("open/closed and competition-distance fields must be aligned to forecast date",),
            selected=False,
        ),
    )


def data_access_instructions(dataset: PublicDatasetName = "m5") -> tuple[str, ...]:
    """Return reproducible access steps without bundling restricted raw files."""
    if dataset != "m5":
        raise ValueError(f"Unsupported public dataset: {dataset}")
    return (
        "Create or sign in to a Kaggle account.",
        "Open https://www.kaggle.com/competitions/m5-forecasting-accuracy and accept the competition terms.",
        "Download the competition data with the Kaggle UI or `kaggle competitions download -c m5-forecasting-accuracy`.",
        "Extract `calendar.csv`, `sales_train_validation.csv`, and `sell_prices.csv` into a local raw directory.",
        "Run checksum validation if your benchmark config contains expected SHA-256 values.",
    )


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_m5_files(
    raw_dir: Path,
    expected_checksums: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate required M5 files and optional SHA-256 checksums."""
    missing = [name for name in M5_REQUIRED_FILES if not (raw_dir / name).exists()]
    if missing:
        instructions = "; ".join(data_access_instructions("m5"))
        raise FileNotFoundError(f"Missing M5 files {missing}. {instructions}")

    checksums = {name: sha256_file(raw_dir / name) for name in M5_REQUIRED_FILES}
    if expected_checksums:
        mismatched = {
            name: checksums[name]
            for name, expected in expected_checksums.items()
            if name in checksums and checksums[name] != expected
        }
        if mismatched:
            raise ValueError(f"Checksum mismatch: {mismatched}")
    return checksums


def known_m5_leakage_fields(raw_dir: Path, *, allowed_last_day: int = 1913) -> tuple[str, ...]:
    """List raw files or columns that should be excluded from training."""
    issues: list[str] = []
    for pattern in M5_LEAKAGE_PATTERNS:
        if pattern.endswith(".csv") and (raw_dir / pattern).exists():
            issues.append(pattern)
    sales_path = raw_dir / "sales_train_validation.csv"
    if sales_path.exists():
        header = pd.read_csv(sales_path, nrows=0)
        for column in header.columns:
            if column.startswith("d_"):
                day_number = _day_number(column)
                if day_number is not None and day_number > allowed_last_day:
                    issues.append(column)
    return tuple(sorted(set(issues)))


def load_m5_canonical(config: M5AdapterConfig) -> pd.DataFrame:
    """Convert user-provided M5 files to a canonical daily demand panel."""
    validate_m5_files(config.raw_dir, config.expected_checksums)
    sales = pd.read_csv(config.raw_dir / "sales_train_validation.csv")
    calendar = pd.read_csv(config.raw_dir / "calendar.csv")
    prices = pd.read_csv(config.raw_dir / "sell_prices.csv")

    day_columns = _selected_day_columns(sales, config.first_day, config.last_day)
    sampled_sales = _deterministic_series_sample(sales, max_series=config.max_series, seed=config.seed)
    melted = sampled_sales.melt(
        id_vars=["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"],
        value_vars=day_columns,
        var_name="d",
        value_name="demand",
    )
    calendar_subset = _calendar_subset(calendar)
    frame = melted.merge(calendar_subset, on="d", how="left", validate="many_to_one")
    frame = frame.merge(
        prices[["store_id", "item_id", "wm_yr_wk", "sell_price"]],
        on=["store_id", "item_id", "wm_yr_wk"],
        how="left",
        validate="many_to_one",
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["product_id"] = frame["item_id"].astype(str)
    frame["demand"] = pd.to_numeric(frame["demand"], errors="coerce").fillna(0.0).clip(lower=0)
    frame["price"] = pd.to_numeric(frame["sell_price"], errors="coerce")
    frame["price"] = frame["price"].fillna(frame.groupby("product_id")["price"].transform("median")).fillna(1.0)
    event_active = frame[["event_name_1", "event_name_2"]].notna().any(axis=1)
    snap_active = frame[["snap_CA", "snap_TX", "snap_WI"]].fillna(False).astype(bool).any(axis=1)
    frame["promotion"] = (event_active | snap_active).astype(int)

    supplements = _supplement_operational_fields(frame)
    canonical = pd.concat([frame.reset_index(drop=True), supplements.reset_index(drop=True)], axis=1)
    columns = [
        "date",
        "store_id",
        "product_id",
        "demand",
        "price",
        "promotion",
        "shelf_life_days",
        "lead_time_days",
        "unit_cost",
        "unit_margin",
        "waste_cost",
        "shrinkage_rate",
        "record_error_std",
        "source_dataset",
        "source_item_id",
        "source_department_id",
        "source_category_id",
        "source_state_id",
        "source_day_key",
        "price_observed",
        "simulated_inventory_fields",
    ]
    canonical["source_dataset"] = "m5"
    canonical["source_item_id"] = canonical["item_id"].astype(str)
    canonical["source_department_id"] = canonical["dept_id"].astype(str)
    canonical["source_category_id"] = canonical["cat_id"].astype(str)
    canonical["source_state_id"] = canonical["state_id"].astype(str)
    canonical["source_day_key"] = canonical["d"].astype(str)
    canonical["price_observed"] = canonical["sell_price"].notna()
    canonical["simulated_inventory_fields"] = True
    return canonical[columns].sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)


def check_date_completeness(frame: pd.DataFrame) -> pd.DataFrame:
    """Return date completeness diagnostics by store-product series."""
    required = {"date", "store_id", "product_id"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Frame is missing columns: {missing}")
    prepared = frame.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    rows: list[dict[str, object]] = []
    for (store_id, product_id), group in prepared.groupby(["store_id", "product_id"], sort=True):
        dates = pd.Series(group["date"].unique()).sort_values()
        expected = pd.date_range(dates.min(), dates.max(), freq="D")
        duplicate_count = int(group.duplicated(["date", "store_id", "product_id"]).sum())
        rows.append(
            {
                "store_id": str(store_id),
                "product_id": str(product_id),
                "start_date": pd.Timestamp(dates.iloc[0]).date().isoformat(),
                "end_date": pd.Timestamp(dates.iloc[-1]).date().isoformat(),
                "observed_days": len(dates),
                "expected_days": len(expected),
                "missing_days": int(len(expected) - len(dates)),
                "duplicate_rows": duplicate_count,
                "complete": len(dates) == len(expected) and duplicate_count == 0,
            }
        )
    return pd.DataFrame(rows)


def run_public_retail_benchmark(
    raw_dir: Path,
    output_dir: Path,
    config: PublicBenchmarkConfig | None = None,
) -> dict[str, str]:
    """Run a small rolling-origin benchmark on user-provided M5 data."""
    effective_config = config or PublicBenchmarkConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical = load_m5_canonical(
        M5AdapterConfig(
            raw_dir=raw_dir,
            max_series=effective_config.max_series,
            seed=effective_config.seed,
        )
    )
    completeness = check_date_completeness(canonical)
    metrics = _rolling_benchmark(canonical, effective_config)
    comparison = _synthetic_comparison(canonical)

    canonical.head(500).to_csv(output_dir / "canonical_sample.csv", index=False)
    completeness.to_csv(output_dir / "date_completeness.csv", index=False)
    metrics.to_csv(output_dir / "forecast_metrics.csv", index=False)
    (output_dir / "benchmark_manifest.json").write_text(
        json.dumps(
            {
                "dataset": "m5",
                "config": asdict(effective_config),
                "data_access": data_access_instructions("m5"),
                "leakage_fields_present": known_m5_leakage_fields(raw_dir),
                "simulated_fields": [
                    "shelf_life_days",
                    "lead_time_days",
                    "unit_cost",
                    "unit_margin",
                    "waste_cost",
                    "shrinkage_rate",
                    "record_error_std",
                ],
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
    (output_dir / "synthetic_comparison.md").write_text(comparison, encoding="utf-8")
    return {
        "canonical_sample": str(output_dir / "canonical_sample.csv"),
        "date_completeness": str(output_dir / "date_completeness.csv"),
        "forecast_metrics": str(output_dir / "forecast_metrics.csv"),
        "manifest": str(output_dir / "benchmark_manifest.json"),
        "synthetic_comparison": str(output_dir / "synthetic_comparison.md"),
    }


def _rolling_benchmark(frame: pd.DataFrame, config: PublicBenchmarkConfig) -> pd.DataFrame:
    features = build_features(frame)
    windows = rolling_origin_cutoffs(
        features["date"],
        minimum_train_days=config.minimum_train_days,
        horizon_days=config.horizon_days,
        step_days=config.step_days,
    )
    if not windows:
        raise ValueError("Not enough dates for rolling-origin benchmark")

    rows: list[dict[str, object]] = []
    feature_names = [
        column
        for column in feature_columns(features)
        if pd.api.types.is_numeric_dtype(features[column])
    ]
    for window_index, (train_end, test_end) in enumerate(windows):
        train = features.loc[pd.to_datetime(features["date"]) <= train_end]
        test = features.loc[
            (pd.to_datetime(features["date"]) > train_end) & (pd.to_datetime(features["date"]) <= test_end)
        ]
        if train.empty or test.empty:
            continue
        rows.extend(_seasonal_metric_rows(train, test, config.quantiles, window_index, train_end, test_end))
        rows.extend(_intermittent_metric_rows(train, test, config.quantiles, window_index, train_end, test_end))
        rows.extend(
            _quantile_boosting_metric_rows(
                train,
                test,
                feature_names,
                config.quantiles,
                window_index,
                train_end,
                test_end,
                config.seed,
            )
        )
    return pd.DataFrame(rows).sort_values(["window", "model", "metric"]).reset_index(drop=True)


def _seasonal_metric_rows(
    train: pd.DataFrame,
    test: pd.DataFrame,
    quantiles: tuple[float, ...],
    window_index: int,
    train_end: pd.Timestamp,
    test_end: pd.Timestamp,
) -> list[dict[str, object]]:
    model = SeasonalNaiveQuantileForecaster(quantiles=quantiles, min_history=2).fit(train)
    predictions = model.predict(test)
    return _metric_rows("seasonal_naive", test["demand"], predictions, quantiles, window_index, train_end, test_end)


def _intermittent_metric_rows(
    train: pd.DataFrame,
    test: pd.DataFrame,
    quantiles: tuple[float, ...],
    window_index: int,
    train_end: pd.Timestamp,
    test_end: pd.Timestamp,
) -> list[dict[str, object]]:
    lookup = {
        key: sba_intermittent_forecast(group["demand"])
        for key, group in train.groupby(["store_id", "product_id"], sort=True)
    }
    fallback = sba_intermittent_forecast(train["demand"])
    point = np.array(
        [
            lookup.get((row["store_id"], row["product_id"]), fallback)
            for _, row in test.iterrows()
        ],
        dtype=float,
    )
    columns = [f"q{round(quantile * 100):02d}" for quantile in quantiles]
    spread = np.maximum(point * 0.30, 1.0)
    matrix = np.column_stack(
        [
            np.maximum(point + (quantile - 0.5) * 2.0 * spread, 0.0)
            for quantile in quantiles
        ]
    )
    predictions = pd.DataFrame(np.maximum.accumulate(matrix, axis=1), columns=columns, index=test.index)
    return _metric_rows("sba_intermittent", test["demand"], predictions, quantiles, window_index, train_end, test_end)


def _quantile_boosting_metric_rows(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_names: list[str],
    quantiles: tuple[float, ...],
    window_index: int,
    train_end: pd.Timestamp,
    test_end: pd.Timestamp,
    seed: int,
) -> list[dict[str, object]]:
    calibration_cutoff = pd.Timestamp(train["date"].max()) - pd.Timedelta(days=14)
    fit_frame = train.loc[pd.to_datetime(train["date"]) <= calibration_cutoff]
    calibration = train.loc[pd.to_datetime(train["date"]) > calibration_cutoff]
    if fit_frame.empty or calibration.empty:
        fit_frame = train
        calibration = train
    model = QuantileForecaster(
        quantiles=quantiles,
        max_iter=40,
        min_samples_leaf=3,
        random_state=seed + window_index,
    ).fit(fit_frame[feature_names], fit_frame["demand"])
    calibration_predictions = model.predict(calibration[feature_names])
    test_predictions = model.predict(test[feature_names])
    if len(quantiles) >= 3:
        calibrator = ConformalIntervalCalibrator.fit(
            calibration["demand"],
            calibration_predictions,
            f"q{round(quantiles[0] * 100):02d}",
            f"q{round(quantiles[-1] * 100):02d}",
            miscoverage=quantiles[0] + (1.0 - quantiles[-1]),
        )
        test_predictions = calibrator.transform(test_predictions)
    return _metric_rows("quantile_boosting", test["demand"], test_predictions, quantiles, window_index, train_end, test_end)


def _metric_rows(
    model_name: str,
    target: pd.Series,
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
    window_index: int,
    train_end: pd.Timestamp,
    test_end: pd.Timestamp,
) -> list[dict[str, object]]:
    metrics = evaluate_quantile_forecast(target, predictions, quantiles)
    rows = [
        {
            "window": window_index,
            "train_end": train_end.date().isoformat(),
            "test_end": test_end.date().isoformat(),
            "model": model_name,
            "metric": "empirical_coverage",
            "value": metrics["empirical_coverage"],
            "rows": metrics["rows"],
        },
        {
            "window": window_index,
            "train_end": train_end.date().isoformat(),
            "test_end": test_end.date().isoformat(),
            "model": model_name,
            "metric": "mean_interval_width",
            "value": metrics["mean_interval_width"],
            "rows": metrics["rows"],
        },
        {
            "window": window_index,
            "train_end": train_end.date().isoformat(),
            "test_end": test_end.date().isoformat(),
            "model": model_name,
            "metric": "approximate_crps",
            "value": metrics["approximate_crps"],
            "rows": metrics["rows"],
        },
    ]
    for column, value in metrics["pinball_loss"].items():
        rows.append(
            {
                "window": window_index,
                "train_end": train_end.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "model": model_name,
                "metric": f"pinball_loss_{column}",
                "value": value,
                "rows": metrics["rows"],
            }
        )
    return rows


def _selected_day_columns(sales: pd.DataFrame, first_day: int, last_day: int | None) -> list[str]:
    day_columns = [column for column in sales.columns if column.startswith("d_")]
    parsed = [(column, _day_number(column)) for column in day_columns]
    selected = [
        column
        for column, day_number in parsed
        if day_number is not None
        and day_number >= first_day
        and (last_day is None or day_number <= last_day)
    ]
    if not selected:
        raise ValueError("No M5 day columns selected")
    return sorted(selected, key=lambda column: _day_number(column) or 0)


def _day_number(column: str) -> int | None:
    try:
        return int(column.removeprefix("d_"))
    except ValueError:
        return None


def _calendar_subset(calendar: pd.DataFrame) -> pd.DataFrame:
    required = {"d", "date", "wm_yr_wk"}
    missing = sorted(required.difference(calendar.columns))
    if missing:
        raise ValueError(f"Calendar is missing columns: {missing}")
    prepared = calendar.copy()
    for column in ("event_name_1", "event_name_2", "snap_CA", "snap_TX", "snap_WI"):
        if column not in prepared.columns:
            prepared[column] = np.nan
    return prepared[["d", "date", "wm_yr_wk", "event_name_1", "event_name_2", "snap_CA", "snap_TX", "snap_WI"]]


def _deterministic_series_sample(sales: pd.DataFrame, *, max_series: int, seed: int) -> pd.DataFrame:
    required = {"id", "item_id", "dept_id", "cat_id", "store_id", "state_id"}
    missing = sorted(required.difference(sales.columns))
    if missing:
        raise ValueError(f"Sales file is missing columns: {missing}")
    if max_series < 1:
        raise ValueError("max_series must be positive")
    prepared = sales.copy()
    key = prepared["id"].astype(str) + f"|{seed}"
    prepared["_sample_rank"] = key.map(lambda value: hashlib.sha256(value.encode()).hexdigest())
    return prepared.sort_values("_sample_rank").head(max_series).drop(columns=["_sample_rank"])


def _supplement_operational_fields(frame: pd.DataFrame) -> pd.DataFrame:
    product_key = frame["item_id"].astype(str)
    category = frame["cat_id"].astype(str)
    digest = product_key.map(lambda value: int(hashlib.sha256(value.encode()).hexdigest()[:8], 16))
    shelf_life = np.where(category.str.lower().eq("foods"), 5, 14)
    return pd.DataFrame(
        {
            "shelf_life_days": shelf_life.astype(int),
            "lead_time_days": (1 + digest % 2).astype(int),
            "unit_cost": np.maximum(frame["price"].to_numpy(dtype=float) * 0.55, 0.10),
            "unit_margin": np.maximum(frame["price"].to_numpy(dtype=float) * 0.30, 0.10),
            "waste_cost": np.maximum(frame["price"].to_numpy(dtype=float) * 0.05, 0.01),
            "shrinkage_rate": 0.01,
            "record_error_std": 1.0,
        }
    ).reset_index(drop=True)


def _synthetic_comparison(frame: pd.DataFrame) -> str:
    demand = pd.to_numeric(frame["demand"], errors="coerce").fillna(0.0)
    zero_share = float((demand <= 0.0).mean())
    series_count = int(frame[["store_id", "product_id"]].drop_duplicates().shape[0])
    return "\n".join(
        [
            "# Public Dataset and Synthetic Generator Comparison",
            "",
            f"- Public benchmark rows: {len(frame)}.",
            f"- Public benchmark series: {series_count}.",
            f"- Public zero-demand share: {zero_share:.3f}.",
            "- Public observations support demand-forecast comparisons on real item-store sales.",
            "- Inventory, shelf-life, waste, shrinkage, and lead-time columns are synthetic supplements in this adapter.",
            "- Synthetic generator results remain the evidence source for inventory-mechanics stress tests.",
            "",
        ]
    )
