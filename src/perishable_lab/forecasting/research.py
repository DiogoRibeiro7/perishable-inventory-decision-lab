"""Research-track probabilistic forecasters and comparison utilities."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.evaluation.reporting import paired_block_bootstrap_difference
from perishable_lab.evaluation.splits import three_way_temporal_split
from perishable_lab.features import build_features, feature_columns
from perishable_lab.forecasting.baselines import SeasonalNaiveQuantileForecaster
from perishable_lab.forecasting.conformal import ConformalIntervalCalibrator
from perishable_lab.forecasting.metrics import evaluate_quantile_forecast
from perishable_lab.forecasting.quantile import QuantileForecaster, quantile_column


class ResearchForecaster(Protocol):
    """Small protocol shared by research-track forecasters."""

    quantiles: tuple[float, ...]

    def fit(self, frame: pd.DataFrame) -> ResearchForecaster:
        """Fit from a feature-enriched daily demand frame."""
        ...

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return non-negative monotone quantile predictions."""
        ...


@dataclass(frozen=True)
class ResearchModelSpec:
    """Manifest entry for a model admitted to the research track."""

    name: str
    family: str
    selected: bool
    selection_reason: str
    production_risk: str


@dataclass(frozen=True)
class ResearchExperimentConfig:
    """Controls for a disciplined research-track comparison."""

    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    seed: int = 42
    service_quantile: float = 0.9
    bootstrap_blocks: int = 200
    minimum_operational_improvement: float = 0.02


@dataclass(frozen=True)
class ResearchExperimentManifest:
    """Reproducibility manifest for a research comparison."""

    experiment_id: str
    seed: int
    quantiles: tuple[float, ...]
    train_end: str
    calibration_end: str
    feature_columns: tuple[str, ...]
    selected_models: tuple[str, ...]
    baseline_model: str


@dataclass(frozen=True)
class ResearchDecision:
    """Keep/reject recommendation for a research candidate."""

    model: str
    decision: str
    reason: str
    mean_cost_delta: float
    confidence_interval: tuple[float, float]
    production_path: tuple[str, ...]


@dataclass
class NegativeBinomialQuantileForecaster:
    """Distributional count baseline with empirical zero mass and overdispersion."""

    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    group_columns: tuple[str, ...] = ("store_id", "product_id")
    target_column: str = "demand"
    min_history: int = 8
    sample_size: int = 3000
    seed: int = 42
    global_values_: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    group_values_: dict[tuple[object, ...], NDArray[np.float64]] = field(default_factory=dict)

    def fit(self, frame: pd.DataFrame) -> NegativeBinomialQuantileForecaster:
        """Store group histories used for parametric count predictions."""
        _require_columns(frame, (*self.group_columns, self.target_column))
        self.global_values_ = frame[self.target_column].to_numpy(dtype=float)
        self.group_values_.clear()
        for group_key, group in frame.groupby(list(self.group_columns), sort=False):
            key = group_key if isinstance(group_key, tuple) else (group_key,)
            self.group_values_[key] = group[self.target_column].to_numpy(dtype=float)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predict quantiles from zero-inflated negative-binomial samples."""
        if len(self.global_values_) == 0:
            raise RuntimeError("Forecaster must be fitted before prediction")
        _require_columns(frame, self.group_columns)
        rows: list[NDArray[np.float64]] = []
        for _, row in frame.iterrows():
            values = self._history(row)
            samples = _zero_inflated_negative_binomial_samples(
                values,
                self.sample_size,
                _stable_seed(row, self.seed, self.group_columns),
            )
            rows.append(np.quantile(samples, self.quantiles).astype(float))
        matrix = np.maximum.accumulate(np.maximum(np.vstack(rows), 0.0), axis=1)
        return pd.DataFrame(matrix, columns=[quantile_column(q) for q in self.quantiles], index=frame.index)

    def _history(self, row: pd.Series) -> NDArray[np.float64]:
        key = tuple(row[column] for column in self.group_columns)
        values = self.group_values_.get(key)
        if values is not None and len(values) >= self.min_history:
            return values
        return self.global_values_


@dataclass
class ResidualScenarioEnsembleForecaster:
    """Empirical scenario model for residual spread around seasonal quantiles."""

    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    group_columns: tuple[str, ...] = ("store_id", "product_id")
    target_column: str = "demand"
    min_history: int = 8
    scenario_count: int = 500
    seed: int = 42
    baseline_: SeasonalNaiveQuantileForecaster | None = None
    residuals_: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))

    def fit(self, frame: pd.DataFrame) -> ResidualScenarioEnsembleForecaster:
        """Fit the seasonal baseline and residual distribution."""
        self.baseline_ = SeasonalNaiveQuantileForecaster(
            quantiles=(0.5,),
            group_columns=self.group_columns,
            target_column=self.target_column,
            min_history=self.min_history,
        ).fit(frame)
        baseline = self.baseline_.predict(frame)["q50"].to_numpy(dtype=float)
        target = frame[self.target_column].to_numpy(dtype=float)
        self.residuals_ = target - baseline
        if len(self.residuals_) == 0:
            self.residuals_ = np.array([0.0], dtype=float)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predict quantiles by sampling residual scenarios around the baseline median."""
        if self.baseline_ is None:
            raise RuntimeError("Forecaster must be fitted before prediction")
        point = self.baseline_.predict(frame)["q50"].to_numpy(dtype=float)
        rows: list[NDArray[np.float64]] = []
        for row_index, (_, row) in enumerate(frame.iterrows()):
            rng = np.random.default_rng(_stable_seed(row, self.seed + row_index, self.group_columns))
            residuals = rng.choice(self.residuals_, size=self.scenario_count, replace=True)
            scenarios = np.maximum(point[row_index] + residuals, 0.0)
            rows.append(np.quantile(scenarios, self.quantiles).astype(float))
        matrix = np.maximum.accumulate(np.maximum(np.vstack(rows), 0.0), axis=1)
        return pd.DataFrame(matrix, columns=[quantile_column(q) for q in self.quantiles], index=frame.index)


def candidate_model_specs() -> tuple[ResearchModelSpec, ...]:
    """Return the selected research candidates and rejected families."""
    return (
        ResearchModelSpec(
            name="negative_binomial_quantile",
            family="distributional_count_regression",
            selected=True,
            selection_reason="Targets overdispersion and zero-heavy demand with low production complexity.",
            production_risk="Parametric tail assumptions can miscalibrate promoted or censored rows.",
        ),
        ResearchModelSpec(
            name="residual_scenario_ensemble",
            family="scenario_generation",
            selected=True,
            selection_reason="Tests cross-horizon scenario logic without adding a deep temporal stack.",
            production_risk="Residual exchangeability can fail under regime shifts.",
        ),
        ResearchModelSpec(
            name="deep_global_temporal_model",
            family="deep_sequence",
            selected=False,
            selection_reason="Deferred until public and synthetic benchmarks show baseline tail failures that require sequence capacity.",
            production_risk="Higher latency, heavier serialization, and less transparent fallback behavior.",
        ),
        ResearchModelSpec(
            name="bayesian_hierarchical_count",
            family="hierarchical_count",
            selected=False,
            selection_reason="Deferred until sparse-cohort failures dominate the error budget.",
            production_risk="Sampling cost and posterior workflow complexity are not justified yet.",
        ),
    )


def build_research_manifest(
    frame: pd.DataFrame,
    config: ResearchExperimentConfig | None = None,
) -> ResearchExperimentManifest:
    """Create a deterministic experiment manifest from feature-enriched data."""
    effective_config = config or ResearchExperimentConfig()
    featured = build_features(frame)
    split = three_way_temporal_split(featured["date"])
    selected = tuple(spec.name for spec in candidate_model_specs() if spec.selected)
    features = tuple(_numeric_feature_columns(featured))
    digest_payload = json.dumps(
        {
            "rows": len(featured),
            "seed": effective_config.seed,
            "quantiles": effective_config.quantiles,
            "train_end": split.train_end.isoformat(),
            "calibration_end": split.calibration_end.isoformat(),
            "features": features,
            "selected": selected,
        },
        sort_keys=True,
        default=str,
    )
    experiment_id = hashlib.sha256(digest_payload.encode()).hexdigest()[:16]
    return ResearchExperimentManifest(
        experiment_id=experiment_id,
        seed=effective_config.seed,
        quantiles=effective_config.quantiles,
        train_end=split.train_end.date().isoformat(),
        calibration_end=split.calibration_end.date().isoformat(),
        feature_columns=features,
        selected_models=selected,
        baseline_model="quantile_boosting_baseline",
    )


def run_research_comparison(
    frame: pd.DataFrame,
    output_dir: Path | None = None,
    config: ResearchExperimentConfig | None = None,
) -> dict[str, pd.DataFrame | dict[str, object]]:
    """Compare baseline and research candidates on identical splits."""
    effective_config = config or ResearchExperimentConfig()
    featured = build_features(frame)
    split = three_way_temporal_split(featured["date"])
    features = _numeric_feature_columns(featured)
    train = featured.loc[split.train].copy()
    calibration = featured.loc[split.calibration].copy()
    test = featured.loc[split.test].copy()

    manifest = build_research_manifest(frame, effective_config)
    predictions: dict[str, pd.DataFrame] = {}
    timings: dict[str, dict[str, float]] = {}

    baseline = QuantileForecaster(
        quantiles=effective_config.quantiles,
        max_iter=40,
        min_samples_leaf=3,
        random_state=effective_config.seed,
    )
    predictions["quantile_boosting_baseline"], timings["quantile_boosting_baseline"] = _fit_predict_baseline(
        baseline,
        train,
        calibration,
        test,
        features,
        effective_config.quantiles,
    )

    nb = NegativeBinomialQuantileForecaster(
        quantiles=effective_config.quantiles,
        seed=effective_config.seed,
    )
    predictions["negative_binomial_quantile"], timings["negative_binomial_quantile"] = _fit_predict_research(
        nb,
        train,
        test,
    )
    ensemble = ResidualScenarioEnsembleForecaster(
        quantiles=effective_config.quantiles,
        seed=effective_config.seed,
    )
    predictions["residual_scenario_ensemble"], timings["residual_scenario_ensemble"] = _fit_predict_research(
        ensemble,
        train,
        test,
    )

    forecast_rows: list[dict[str, object]] = []
    policy_rows: list[dict[str, object]] = []
    ablation_rows: list[dict[str, object]] = []
    for model_name, prediction in predictions.items():
        forecast_rows.extend(_forecast_metric_rows(model_name, test["demand"], prediction, effective_config.quantiles))
        policy_rows.extend(_policy_proxy_rows(model_name, test, prediction, effective_config.service_quantile))
        ablation_rows.extend(
            _ablation_rows(model_name, test, prediction, timings[model_name], effective_config.service_quantile)
        )

    forecast_metrics = pd.DataFrame(forecast_rows).sort_values(["model", "metric"]).reset_index(drop=True)
    policy_metrics = pd.DataFrame(policy_rows).sort_values(["model", "date", "store_id", "product_id"]).reset_index(drop=True)
    ablation = pd.DataFrame(ablation_rows).sort_values(["model", "ablation"]).reset_index(drop=True)
    decisions = research_decisions(policy_metrics, effective_config)

    outputs: dict[str, pd.DataFrame | dict[str, object]] = {
        "manifest": asdict(manifest),
        "forecast_metrics": forecast_metrics,
        "policy_metrics": policy_metrics,
        "ablation": ablation,
        "decisions": pd.DataFrame([asdict(decision) for decision in decisions]),
    }
    if output_dir is not None:
        _write_research_outputs(outputs, output_dir)
    return outputs


def research_decisions(
    policy_metrics: pd.DataFrame,
    config: ResearchExperimentConfig | None = None,
) -> tuple[ResearchDecision, ...]:
    """Return keep/reject decisions using operational cost deltas."""
    effective_config = config or ResearchExperimentConfig()
    baseline = policy_metrics.loc[policy_metrics["model"] == "quantile_boosting_baseline"]
    decisions: list[ResearchDecision] = []
    for raw_model_name, group in policy_metrics.groupby("model", sort=True):
        model_name = str(raw_model_name)
        if model_name == "quantile_boosting_baseline":
            continue
        joined = group.merge(
            baseline[["date", "store_id", "product_id", "proxy_cost"]],
            on=["date", "store_id", "product_id"],
            suffixes=("", "_baseline"),
            validate="one_to_one",
        )
        paired = joined.rename(
            columns={
                "proxy_cost_baseline": "baseline_cost",
                "proxy_cost": "candidate_cost",
            }
        ).sort_values(["date", "store_id", "product_id"])
        delta = paired["candidate_cost"] - paired["baseline_cost"]
        interval = paired_block_bootstrap_difference(
            paired,
            baseline_column="baseline_cost",
            candidate_column="candidate_cost",
            n_resamples=effective_config.bootstrap_blocks,
            seed=effective_config.seed,
        )
        mean_delta = float(delta.mean())
        keep = mean_delta <= -effective_config.minimum_operational_improvement and interval["upper_95"] < 0.0
        decisions.append(
            ResearchDecision(
                model=model_name,
                decision="keep_for_shadow_test" if keep else "reject_for_now",
                reason=(
                    "Operational proxy cost improves beyond threshold with paired uncertainty below zero."
                    if keep
                    else "No reproducible operational improvement large enough to justify added complexity."
                ),
                mean_cost_delta=mean_delta,
                confidence_interval=(float(interval["lower_95"]), float(interval["upper_95"])),
                production_path=(
                    "persist model manifest",
                    "add segmented calibration gates",
                    "run shadow policy comparison",
                    "define rollback to quantile boosting baseline",
                ),
            )
        )
    return tuple(decisions)


def _fit_predict_baseline(
    model: QuantileForecaster,
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    quantiles: tuple[float, ...],
) -> tuple[pd.DataFrame, dict[str, float]]:
    start = time.perf_counter()
    model.fit(train[features], train["demand"])
    fit_seconds = time.perf_counter() - start
    calibration_predictions = model.predict(calibration[features])
    start = time.perf_counter()
    predictions = model.predict(test[features])
    predict_seconds = time.perf_counter() - start
    if len(quantiles) >= 2:
        calibrator = ConformalIntervalCalibrator.fit(
            calibration["demand"],
            calibration_predictions,
            quantile_column(quantiles[0]),
            quantile_column(quantiles[-1]),
            miscoverage=quantiles[0] + (1.0 - quantiles[-1]),
        )
        predictions = calibrator.transform(predictions)
    return predictions, {"fit_seconds": fit_seconds, "predict_seconds": predict_seconds}


def _fit_predict_research(
    model: ResearchForecaster,
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    start = time.perf_counter()
    model.fit(train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    predictions = model.predict(test)
    predict_seconds = time.perf_counter() - start
    return predictions, {"fit_seconds": fit_seconds, "predict_seconds": predict_seconds}


def _forecast_metric_rows(
    model_name: str,
    target: pd.Series,
    predictions: pd.DataFrame,
    quantiles: tuple[float, ...],
) -> list[dict[str, object]]:
    metrics = evaluate_quantile_forecast(target, predictions, quantiles)
    rows = [
        {"model": model_name, "metric": "empirical_coverage", "value": metrics["empirical_coverage"], "rows": metrics["rows"]},
        {"model": model_name, "metric": "mean_interval_width", "value": metrics["mean_interval_width"], "rows": metrics["rows"]},
        {"model": model_name, "metric": "approximate_crps", "value": metrics["approximate_crps"], "rows": metrics["rows"]},
    ]
    for column, value in metrics["pinball_loss"].items():
        rows.append({"model": model_name, "metric": f"pinball_loss_{column}", "value": value, "rows": metrics["rows"]})
    return rows


def _policy_proxy_rows(
    model_name: str,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    service_quantile: float,
) -> list[dict[str, object]]:
    service_column = quantile_column(service_quantile)
    if service_column not in predictions.columns:
        service_column = predictions.columns[-1]
    rows: list[dict[str, object]] = []
    service_values = predictions[service_column].to_numpy(dtype=float)
    for row_index, (_index, row) in enumerate(test.iterrows()):
        demand = float(row["demand"])
        target = service_values[row_index] * max(1.0, float(row.get("lead_time_days", 1.0)))
        inventory = max(0.0, float(row.get("observed_inventory", 0.0)))
        order = max(0.0, round(target - inventory))
        fulfilled = min(order + inventory, demand)
        lost = max(demand - fulfilled, 0.0)
        waste = max(order + inventory - demand, 0.0)
        unit_margin = float(row.get("unit_margin", 1.0))
        unit_cost = float(row.get("unit_cost", 1.0))
        waste_cost = float(row.get("waste_cost", 0.0))
        proxy_cost = lost * unit_margin + waste * (unit_cost + waste_cost)
        rows.append(
            {
                "model": model_name,
                "date": pd.Timestamp(row["date"]).date().isoformat(),
                "store_id": str(row["store_id"]),
                "product_id": str(row["product_id"]),
                "order_quantity": order,
                "fulfilled_units": fulfilled,
                "lost_sales_units": lost,
                "waste_units": waste,
                "proxy_cost": proxy_cost,
            }
        )
    return rows


def _ablation_rows(
    model_name: str,
    test: pd.DataFrame,
    predictions: pd.DataFrame,
    timing: dict[str, float],
    service_quantile: float,
) -> list[dict[str, object]]:
    policy = pd.DataFrame(_policy_proxy_rows(model_name, test, predictions, service_quantile))
    return [
        {"model": model_name, "ablation": "all_features", "metric": "mean_proxy_cost", "value": float(policy["proxy_cost"].mean())},
        {"model": model_name, "ablation": "training_stability", "metric": "fit_seconds", "value": timing["fit_seconds"]},
        {"model": model_name, "ablation": "latency", "metric": "predict_seconds", "value": timing["predict_seconds"]},
        {"model": model_name, "ablation": "fallback", "metric": "finite_prediction_rate", "value": float(np.isfinite(predictions.to_numpy(dtype=float)).mean())},
    ]


def _write_research_outputs(outputs: dict[str, pd.DataFrame | dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        if isinstance(payload, pd.DataFrame):
            payload.to_csv(output_dir / f"{name}.csv", index=False)
        else:
            (output_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _numeric_feature_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in feature_columns(frame) if pd.api.types.is_numeric_dtype(frame[column])]


def _zero_inflated_negative_binomial_samples(
    values: NDArray[np.float64],
    size: int,
    seed: int,
) -> NDArray[np.float64]:
    clipped = np.maximum(values.astype(float), 0.0)
    mean = max(float(np.mean(clipped)), 1e-6)
    variance = max(float(np.var(clipped, ddof=1)) if len(clipped) > 1 else mean, mean + 1e-6)
    zero_probability = min(max(float(np.mean(clipped <= 0.0)), 0.0), 0.95)
    dispersion = max(mean * mean / max(variance - mean, 1e-6), 0.25)
    probability = dispersion / (dispersion + mean)
    rng = np.random.default_rng(seed)
    samples = rng.negative_binomial(dispersion, probability, size=size).astype(float)
    zero_mask = rng.random(size) < zero_probability
    samples[zero_mask] = 0.0
    return samples


def _stable_seed(row: pd.Series, seed: int, group_columns: tuple[str, ...]) -> int:
    raw = "|".join([str(seed), *(str(row[column]) for column in group_columns), str(row.get("date", ""))])
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Frame is missing columns: {missing}")


__all__ = [
    "NegativeBinomialQuantileForecaster",
    "ResearchDecision",
    "ResearchExperimentConfig",
    "ResearchExperimentManifest",
    "ResearchModelSpec",
    "ResidualScenarioEnsembleForecaster",
    "build_research_manifest",
    "candidate_model_specs",
    "research_decisions",
    "run_research_comparison",
]
