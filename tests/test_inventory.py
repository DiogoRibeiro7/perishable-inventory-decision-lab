import pandas as pd

from perishable_lab.inventory.policies import MedianPolicy, PolicyContext, QuantileBaseStockPolicy
from perishable_lab.inventory.simulator import simulate_series


def test_policy_never_returns_negative_order() -> None:
    context = PolicyContext(
        forecast_target=5.0,
        forecast_median=3.0,
        observed_inventory=100.0,
        pipeline_inventory=0.0,
        lead_time_days=1,
        shelf_life_days=3,
    )
    assert MedianPolicy().order(context) == 0
    assert QuantileBaseStockPolicy().order(context) == 0


def test_inventory_simulator_conserves_daily_demand() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=6),
            "demand": [2, 2, 2, 2, 2, 2],
            "q50": [2.0] * 6,
            "service_q90": [3.0] * 6,
            "shelf_life_days": [3] * 6,
            "lead_time_days": [1] * 6,
            "unit_cost": [1.0] * 6,
            "unit_margin": [1.0] * 6,
            "waste_cost": [0.1] * 6,
            "shrinkage_rate": [0.0] * 6,
            "record_error_std": [0.0] * 6,
        }
    )
    result = simulate_series(
        frame,
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
    )

    assert ((result["fulfilled"] + result["lost_sales"]) == result["demand"]).all()
    assert (result["ending_inventory"] >= 0).all()
