from pathlib import Path

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
    assert result["forecast_metrics"]["rows"] > 0
