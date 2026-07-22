from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from perishable_lab.cli import app
from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.forecasting.research import (
    NegativeBinomialQuantileForecaster,
    ResidualScenarioEnsembleForecaster,
    build_research_manifest,
    candidate_model_specs,
    run_research_comparison,
)


def _frame() -> pd.DataFrame:
    return generate_daily_demand(SyntheticDataSpec(days=120, stores=2, products=3, seed=21))


def test_candidate_selection_limits_initial_research_models() -> None:
    specs = candidate_model_specs()
    selected = [spec for spec in specs if spec.selected]

    assert len(selected) <= 2
    assert {spec.name for spec in selected} == {
        "negative_binomial_quantile",
        "residual_scenario_ensemble",
    }


def test_research_forecasters_emit_monotone_quantiles() -> None:
    frame = _frame().head(90)
    test = frame.tail(12)

    for model in (
        NegativeBinomialQuantileForecaster(sample_size=500, seed=3),
        ResidualScenarioEnsembleForecaster(scenario_count=200, seed=3),
    ):
        predictions = model.fit(frame).predict(test)
        assert list(predictions.columns) == ["q10", "q50", "q90"]
        assert (predictions >= 0).all().all()
        assert (predictions["q10"] <= predictions["q50"]).all()
        assert (predictions["q50"] <= predictions["q90"]).all()


def test_manifest_is_deterministic_and_records_identical_split_surface() -> None:
    frame = _frame()
    first = build_research_manifest(frame)
    second = build_research_manifest(frame)

    assert first == second
    assert first.baseline_model == "quantile_boosting_baseline"
    assert first.selected_models == ("negative_binomial_quantile", "residual_scenario_ensemble")
    assert first.train_end < first.calibration_end


def test_research_comparison_includes_baseline_metrics_and_decisions(tmp_path: Path) -> None:
    outputs = run_research_comparison(_frame(), tmp_path)
    forecast_metrics = outputs["forecast_metrics"]
    decisions = outputs["decisions"]

    assert isinstance(forecast_metrics, pd.DataFrame)
    assert {"quantile_boosting_baseline", "negative_binomial_quantile", "residual_scenario_ensemble"}.issubset(
        set(forecast_metrics["model"])
    )
    assert isinstance(decisions, pd.DataFrame)
    assert set(decisions["decision"]).issubset({"keep_for_shadow_test", "reject_for_now"})
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "ablation.csv").exists()


def test_research_comparison_cli_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "canonical.csv"
    output_dir = tmp_path / "out"
    _frame().to_csv(input_path, index=False)

    result = CliRunner().invoke(
        app,
        [
            "research-comparison",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--bootstrap-blocks",
            "20",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "forecast_metrics.csv").exists()
