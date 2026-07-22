from pathlib import Path

import pandas as pd

from perishable_lab.config import AppConfig, ForecastConfig, SimulationConfig
from perishable_lab.pipelines.demo import run_demo


def test_demo_pipeline_writes_expected_outputs(tmp_path: Path) -> None:
    config = AppConfig(
        simulation=SimulationConfig(days=90, stores=1, products=2, seed=11),
        forecasting=ForecastConfig(max_iter=20, min_samples_leaf=5),
    )
    result = run_demo(config, tmp_path)

    assert (tmp_path / "forecast_metrics.json").exists()
    assert (tmp_path / "policy_metrics.csv").exists()
    assert (tmp_path / "evaluation_report.json").exists()
    assert result["forecast_metrics"]["rows"] > 0
    assert result["forecast_metrics"]["demand_censoring"]["method"] == "flag_exclude"
    assert result["forecast_metrics"]["demand_censoring"]["censored_rows"] == 0
    assert result["forecast_metrics"]["demand_censoring"]["training_weight_mean"] == 1.0
    assert {
        "store_id",
        "product_id",
        "demand_volume_band",
        "shelf_life_band",
    } <= {
        segment["segment_type"]
        for segment in result["forecast_metrics"]["censoring_segments"]
    }

    forecasts = pd.read_csv(tmp_path / "forecast_predictions.csv")
    policies = pd.read_csv(tmp_path / "policy_metrics.csv")

    for column in ("generated_at_utc", "config_hash", "model_version"):
        assert column in forecasts.columns
        assert column in policies.columns

    assert "policy_version" in policies.columns
    assert forecasts["config_hash"].nunique() == 1
    assert policies["policy_version"].nunique() == 3
