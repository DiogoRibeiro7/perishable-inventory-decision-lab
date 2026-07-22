import pandas as pd

from perishable_lab.inventory.policies import (
    AgeAwareBaseStockPolicy,
    ConstrainedBaseStockPolicy,
    MedianPolicy,
    OrderingConstraints,
    PolicyContext,
    QuantileBaseStockPolicy,
    critical_fractile,
)
from perishable_lab.inventory.simulator import SimulationControls, simulate_series


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


def test_constrained_policy_applies_case_pack_minimum_and_capacity() -> None:
    context = PolicyContext(
        forecast_target=9.0,
        forecast_median=5.0,
        observed_inventory=1.0,
        pipeline_inventory=0.0,
        lead_time_days=1,
        shelf_life_days=3,
    )
    policy = ConstrainedBaseStockPolicy(
        constraints=OrderingConstraints(
            case_pack=4,
            minimum_order_quantity=4,
            storage_capacity_units=7,
        )
    )

    assert policy.order(context) == 4


def test_age_aware_policy_discounts_expiring_inventory() -> None:
    context = PolicyContext(
        forecast_target=8.0,
        forecast_median=5.0,
        observed_inventory=8.0,
        pipeline_inventory=0.0,
        lead_time_days=1,
        shelf_life_days=2,
        expiring_inventory=4.0,
    )

    assert QuantileBaseStockPolicy().order(context) == 0
    assert AgeAwareBaseStockPolicy().order(context) == 4


def test_higher_underage_cost_increases_critical_fractile() -> None:
    low_margin = critical_fractile(unit_margin=1.0, unit_cost=2.0, waste_cost=0.5)
    high_margin = critical_fractile(unit_margin=4.0, unit_cost=2.0, waste_cost=0.5)

    assert high_margin > low_margin


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


def test_order_controls_apply_case_pack_and_capacity() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=2),
            "demand": [0, 0],
            "q50": [10.0, 10.0],
            "service_q90": [10.0, 10.0],
            "shelf_life_days": [3, 3],
            "lead_time_days": [1, 1],
            "unit_cost": [1.0, 1.0],
            "unit_margin": [1.0, 1.0],
            "waste_cost": [0.1, 0.1],
            "shrinkage_rate": [0.0, 0.0],
            "record_error_std": [0.0, 0.0],
        }
    )

    result = simulate_series(
        frame,
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        controls=SimulationControls(case_pack=4, storage_capacity_units=5),
    )

    assert result.loc[0, "requested_order_quantity"] == 10
    assert result.loc[0, "order_quantity"] == 4
    assert result.loc[0, "supplier_filled_quantity"] == 4


def test_supplier_fill_and_lead_time_jitter_are_recorded() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=2),
            "demand": [0, 0],
            "q50": [3.0, 3.0],
            "service_q90": [3.0, 3.0],
            "shelf_life_days": [3, 3],
            "lead_time_days": [1, 1],
            "unit_cost": [1.0, 1.0],
            "unit_margin": [1.0, 1.0],
            "waste_cost": [0.1, 0.1],
            "shrinkage_rate": [0.0, 0.0],
            "record_error_std": [0.0, 0.0],
        }
    )

    result = simulate_series(
        frame,
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        controls=SimulationControls(
            supplier_fill_rate=0.0,
            lead_time_jitter_probability=1.0,
            max_lead_time_jitter_days=1,
        ),
        seed=4,
    )

    assert result.loc[0, "supplier_filled_quantity"] == 0
    assert result.loc[0, "effective_lead_time_days"] == 2
