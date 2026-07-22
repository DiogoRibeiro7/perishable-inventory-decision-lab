from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from perishable_lab.decision import cumulative_quantiles_from_scenarios, generate_demand_scenarios
from perishable_lab.features import build_features
from perishable_lab.inventory.policies import (
    ConstrainedBaseStockPolicy,
    OrderingConstraints,
    PolicyContext,
    QuantileBaseStockPolicy,
)
from perishable_lab.inventory.simulator import SimulationControls, simulate_series
from perishable_lab.publication import store_file_contract


def _random_series(seed: int) -> pd.DataFrame:
    rng = pd.Series(range(12), dtype="int64")
    demand = ((rng * (seed % 5 + 1)) % 9).astype(int)
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=12),
            "demand": demand,
            "q50": demand.rolling(3, min_periods=1).mean().clip(lower=1).astype(float),
            "service_q90": (demand.rolling(4, min_periods=1).mean() + 3).clip(lower=2).astype(float),
            "shelf_life_days": [3 + seed % 3] * 12,
            "lead_time_days": [1 + seed % 2] * 12,
            "unit_cost": [1.0] * 12,
            "unit_margin": [1.5] * 12,
            "waste_cost": [0.2] * 12,
            "shrinkage_rate": [0.0] * 12,
            "record_error_std": [0.0] * 12,
        }
    )


@pytest.mark.parametrize("seed", [1, 7, 13, 29], ids=lambda seed: f"seed={seed}")
def test_inventory_invariants_hold_for_generated_series(seed: int) -> None:
    result = simulate_series(
        _random_series(seed),
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        controls=SimulationControls(case_pack=2, storage_capacity_units=20),
        seed=seed,
    )

    assert ((result["fulfilled"] + result["lost_sales"]) == result["demand"]).all()
    assert (result["order_quantity"] >= 0).all()
    assert (result["supplier_filled_quantity"] >= 0).all()
    assert (result["ending_inventory"] >= 0).all()
    assert (result["waste_units"] >= 0).all()
    assert (result["fulfilled"] <= result["demand"]).all()


@pytest.mark.parametrize("observed_inventory", [0.0, 2.0, 5.0], ids=lambda value: f"inventory={value}")
def test_policy_order_is_monotone_in_service_forecast(observed_inventory: float) -> None:
    policy = QuantileBaseStockPolicy()
    contexts = [
        PolicyContext(
            forecast_target=float(target),
            forecast_median=target / 2.0,
            observed_inventory=observed_inventory,
            pipeline_inventory=1.0,
            lead_time_days=1,
            shelf_life_days=3,
        )
        for target in [3, 6, 9, 12]
    ]

    orders = [policy.order(context) for context in contexts]

    assert orders == sorted(orders)


@pytest.mark.parametrize("target", [3.0, 8.0, 13.0], ids=lambda value: f"target={value}")
def test_hard_constraints_are_preserved(target: float) -> None:
    policy = ConstrainedBaseStockPolicy(
        constraints=OrderingConstraints(
            case_pack=4,
            minimum_order_quantity=4,
            storage_capacity_units=10,
        )
    )
    context = PolicyContext(
        forecast_target=target,
        forecast_median=target / 2.0,
        observed_inventory=1.0,
        pipeline_inventory=1.0,
        lead_time_days=1,
        shelf_life_days=3,
    )

    order = policy.order(context)

    assert order >= 0
    assert order <= 8
    assert order == 0 or order % 4 == 0


def test_replay_is_deterministic_for_same_seed() -> None:
    frame = _random_series(17)

    first = simulate_series(frame, QuantileBaseStockPolicy(), service_forecast_column="service_q90", seed=17)
    second = simulate_series(frame, QuantileBaseStockPolicy(), service_forecast_column="service_q90", seed=17)

    pd.testing.assert_frame_equal(first, second)


def test_feature_generation_does_not_use_future_demand() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=40),
            "store_id": ["s1"] * 40,
            "product_id": ["p1"] * 40,
            "demand": [5] * 40,
            "unit_cost": [1.0] * 40,
            "unit_margin": [1.0] * 40,
            "waste_cost": [0.1] * 40,
        }
    )
    revised = frame.copy(deep=True)
    revised.loc[revised["date"] > pd.Timestamp("2026-01-25"), "demand"] = 99

    base_features = build_features(frame)
    revised_features = build_features(revised)
    cutoff = pd.Timestamp("2026-01-25")
    columns = ["demand_lag_1", "demand_lag_7", "demand_mean_7", "demand_mean_28"]

    pd.testing.assert_frame_equal(
        base_features.loc[base_features["date"] <= cutoff, ["date", *columns]].reset_index(drop=True),
        revised_features.loc[revised_features["date"] <= cutoff, ["date", *columns]].reset_index(drop=True),
    )


@pytest.mark.parametrize("seed", [3, 11, 19], ids=lambda seed: f"seed={seed}")
def test_quantile_generation_remains_monotone(seed: int) -> None:
    marginals = pd.DataFrame(
        {
            "q05": [1.0, 2.0, 2.0],
            "q50": [4.0, 5.0, 5.0],
            "q95": [9.0, 10.0, 11.0],
        }
    )
    paths = generate_demand_scenarios(
        marginals,
        quantile_columns=("q05", "q50", "q95"),
        scenarios=25,
        seed=seed,
        dependence="independent",
    )
    quantiles = cumulative_quantiles_from_scenarios(paths, quantiles=(0.05, 0.5, 0.95))

    assert quantiles[0.05] <= quantiles[0.5] <= quantiles[0.95]


def test_store_contract_schema_is_stable() -> None:
    frame = pd.DataFrame(
        {
            "business_date": ["2026-01-05"],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "active_order_quantity": [6],
            "unit": ["unit"],
            "policy_version": ["policy-v1"],
            "input_feature_set_hash": ["hash1"],
            "override_reason": [""],
            "generated_at": [datetime(2026, 1, 5, tzinfo=UTC)],
        }
    )

    contract = store_file_contract(frame)

    assert contract.columns.tolist() == [
        "business_date",
        "store_id",
        "product_id",
        "active_order_quantity",
        "unit",
        "policy_version",
        "input_feature_set_hash",
        "override_reason",
    ]
