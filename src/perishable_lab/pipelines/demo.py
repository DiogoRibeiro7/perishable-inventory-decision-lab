"""End-to-end demonstration pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab import __version__
from perishable_lab.config import AppConfig
from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.data.validation import validate_daily_demand
from perishable_lab.evaluation.reporting import build_evaluation_report
from perishable_lab.evaluation.splits import three_way_temporal_split
from perishable_lab.features import TARGET_COLUMN, build_features, feature_columns
from perishable_lab.forecasting.conformal import ConformalIntervalCalibrator
from perishable_lab.forecasting.metrics import evaluate_quantile_forecast
from perishable_lab.forecasting.quantile import (
    QuantileForecaster,
    interpolate_quantile,
    interpolate_rowwise_quantiles,
    quantile_column,
)
from perishable_lab.inventory.policies import (
    MedianPolicy,
    OrderingPolicy,
    QuantileBaseStockPolicy,
    critical_fractile,
)
from perishable_lab.inventory.simulator import SimulationCosts, simulate_panel
from perishable_lab.monitoring.quality import build_monitoring_report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON document with stable formatting."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _config_hash(config: AppConfig) -> str:
    """Return a stable hash for the validated runtime configuration."""
    serialized = config.model_dump_json()
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _with_run_metadata(
    frame: pd.DataFrame,
    *,
    generated_at_utc: str,
    config_hash: str,
    model_version: str,
    policy_version: str | None = None,
) -> pd.DataFrame:
    """Attach run metadata columns to persisted row-level outputs."""
    enriched = frame.copy()
    enriched["generated_at_utc"] = generated_at_utc
    enriched["config_hash"] = config_hash
    enriched["model_version"] = model_version
    if policy_version is not None:
        enriched["policy_version"] = policy_version
    return enriched


def run_demo(config: AppConfig, output_dir: Path) -> dict[str, Any]:
    """Run the complete showcase pipeline and persist its outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at_utc = datetime.now(UTC).isoformat()
    config_hash = _config_hash(config)
    model_version = f"quantile_forecaster:{__version__}"

    spec = SyntheticDataSpec(
        days=config.simulation.days,
        stores=config.simulation.stores,
        products=config.simulation.products,
        seed=config.simulation.seed,
    )
    raw = generate_daily_demand(spec)
    validation = validate_daily_demand(raw)
    if not validation.is_valid:
        raise ValueError(f"Generated data failed validation: {validation.errors}")
    raw.to_csv(output_dir / "synthetic_daily_demand.csv", index=False)

    featured = build_features(raw)
    columns = feature_columns(featured)
    split = three_way_temporal_split(featured["date"])

    model = QuantileForecaster(
        quantiles=config.forecasting.quantiles,
        max_iter=config.forecasting.max_iter,
        learning_rate=config.forecasting.learning_rate,
        max_leaf_nodes=config.forecasting.max_leaf_nodes,
        min_samples_leaf=config.forecasting.min_samples_leaf,
        random_state=config.simulation.seed,
    )
    model.fit(featured.loc[split.train, columns], featured.loc[split.train, TARGET_COLUMN])

    calibration_predictions = model.predict(featured.loc[split.calibration, columns])
    lower_column = quantile_column(config.forecasting.quantiles[0])
    upper_column = quantile_column(config.forecasting.quantiles[-1])
    calibrator = ConformalIntervalCalibrator.fit(
        featured.loc[split.calibration, TARGET_COLUMN],
        calibration_predictions,
        lower_column,
        upper_column,
        miscoverage=config.forecasting.quantiles[0]
        + (1.0 - config.forecasting.quantiles[-1]),
    )

    test = featured.loc[split.test].copy().reset_index(drop=True)
    raw_test_predictions = model.predict(test[columns]).reset_index(drop=True)
    predictions = calibrator.transform(raw_test_predictions)
    service_column = f"service_q{round(config.inventory.service_level * 100):02d}"
    predictions[service_column] = interpolate_quantile(
        predictions,
        config.forecasting.quantiles,
        config.inventory.service_level,
    )
    economic_probabilities: NDArray[np.float64] = np.asarray(
        test.apply(
            lambda row: critical_fractile(
                float(row["unit_margin"]),
                float(row["unit_cost"]),
                float(row["waste_cost"]),
            ),
            axis=1,
        ).to_numpy(dtype=np.float64),
        dtype=np.float64,
    )
    predictions["economic_target"] = interpolate_rowwise_quantiles(
        predictions,
        config.forecasting.quantiles,
        economic_probabilities,
    )
    predictions["economic_critical_fractile"] = economic_probabilities

    prediction_output = pd.concat(
        [
            test[["date", "store_id", "product_id", TARGET_COLUMN]].reset_index(drop=True),
            predictions.reset_index(drop=True),
        ],
        axis=1,
    )
    prediction_output = _with_run_metadata(
        prediction_output,
        generated_at_utc=generated_at_utc,
        config_hash=config_hash,
        model_version=model_version,
    )
    prediction_output.to_csv(output_dir / "forecast_predictions.csv", index=False)

    forecast_metrics = evaluate_quantile_forecast(
        test[TARGET_COLUMN],
        predictions,
        config.forecasting.quantiles,
    )
    forecast_metrics["conformal_adjustment"] = calibrator.adjustment
    _write_json(output_dir / "forecast_metrics.json", forecast_metrics)

    simulation_input = pd.concat(
        [test.reset_index(drop=True), predictions.reset_index(drop=True)], axis=1
    )
    costs = SimulationCosts(
        holding_cost_per_unit_day=config.inventory.holding_cost_per_unit_day
    )
    policy_runs: list[tuple[OrderingPolicy, str]] = [
        (MedianPolicy(), service_column),
        (QuantileBaseStockPolicy(name="fixed_service_level"), service_column),
        (QuantileBaseStockPolicy(name="economic_newsvendor"), "economic_target"),
    ]
    policy_summary_parts: list[pd.DataFrame] = []
    for policy, forecast_column in policy_runs:
        policy_version = f"{policy.name}:{__version__}"
        daily, summary = simulate_panel(
            simulation_input,
            policy,
            service_forecast_column=forecast_column,
            seed=config.simulation.seed,
            costs=costs,
        )
        daily = _with_run_metadata(
            daily,
            generated_at_utc=generated_at_utc,
            config_hash=config_hash,
            model_version=model_version,
            policy_version=policy_version,
        )
        daily.to_csv(output_dir / f"inventory_daily_{policy.name}.csv", index=False)
        summary["generated_at_utc"] = generated_at_utc
        summary["config_hash"] = config_hash
        summary["model_version"] = model_version
        summary["policy_version"] = policy_version
        summary["holding_cost_per_unit_day"] = costs.holding_cost_per_unit_day
        policy_summary_parts.append(summary)

    policy_summary = pd.concat(policy_summary_parts, ignore_index=True)
    aggregate_policy_metrics = (
        policy_summary.groupby("policy", as_index=False)
        .agg(
            demand_units=("demand_units", "sum"),
            fulfilled_units=("fulfilled_units", "sum"),
            total_cost=("total_cost", "sum"),
            ordered_units=("ordered_units", "sum"),
            waste_units=("waste_units", "sum"),
            lost_sales_units=("lost_sales_units", "sum"),
            average_inventory=("average_inventory", "mean"),
            average_order_quantity=("average_order_quantity", "mean"),
            generated_at_utc=("generated_at_utc", "first"),
            config_hash=("config_hash", "first"),
            model_version=("model_version", "first"),
            policy_version=("policy_version", "first"),
        )
    )
    aggregate_policy_metrics["fill_rate"] = (
        aggregate_policy_metrics["fulfilled_units"]
        / aggregate_policy_metrics["demand_units"].clip(lower=1.0)
    )
    aggregate_policy_metrics["lost_sales_rate"] = (
        aggregate_policy_metrics["lost_sales_units"]
        / aggregate_policy_metrics["demand_units"].clip(lower=1.0)
    )
    aggregate_policy_metrics["waste_rate"] = (
        aggregate_policy_metrics["waste_units"]
        / aggregate_policy_metrics["ordered_units"].clip(lower=1.0)
    )
    aggregate_policy_metrics["cost_per_demand_unit"] = (
        aggregate_policy_metrics["total_cost"]
        / aggregate_policy_metrics["demand_units"].clip(lower=1.0)
    )
    aggregate_policy_metrics.to_csv(output_dir / "policy_metrics.csv", index=False)

    monitoring_report = build_monitoring_report(
        test,
        forecast_metrics,
        minimum_coverage=config.monitoring.minimum_coverage,
        maximum_missing_rate=config.monitoring.maximum_missing_rate,
    )
    _write_json(output_dir / "monitoring_report.json", monitoring_report)

    evaluation_report = build_evaluation_report(
        forecast_metrics=forecast_metrics,
        policy_metrics=aggregate_policy_metrics,
        monitoring_report=monitoring_report,
    )
    _write_json(output_dir / "evaluation_report.json", evaluation_report)

    manifest = {
        "created_at_utc": generated_at_utc,
        "package_version": __version__,
        "config_hash": config_hash,
        "model_version": model_version,
        "config": config.model_dump(),
        "data_spec": asdict(spec),
        "feature_columns": columns,
        "train_end": split.train_end.isoformat(),
        "calibration_end": split.calibration_end.isoformat(),
        "test_rows": int(split.test.sum()),
        "artifacts": sorted(path.name for path in output_dir.iterdir()),
    }
    _write_json(output_dir / "run_manifest.json", manifest)

    return {
        "forecast_metrics": forecast_metrics,
        "policy_metrics": aggregate_policy_metrics.to_dict(orient="records"),
        "monitoring": monitoring_report,
        "output_dir": str(output_dir),
    }
