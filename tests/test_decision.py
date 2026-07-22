from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from perishable_lab.decision import (
    DecisionContext,
    DecisionContractError,
    ForecastDistribution,
    InventorySnapshot,
    PendingOrder,
    build_order_recommendation,
    convert_units,
    cumulative_quantiles_from_scenarios,
    generate_demand_scenarios,
    sum_marginal_quantiles_without_dependence,
    validate_decision_context,
)
from perishable_lab.inventory.policies import OrderingConstraints


def _forecast(horizon_days: int = 2) -> ForecastDistribution:
    return ForecastDistribution(
        forecast_id="f1",
        product_id="P001",
        store_id="S001",
        generated_at=datetime(2026, 1, 1, 5, tzinfo=UTC),
        target_start=datetime(2026, 1, 1, 6, tzinfo=UTC),
        horizon_days=horizon_days,
        unit="unit",
        quantiles={0.5: 6.0, 0.9: 10.0},
        model_version="m1",
        distribution_kind="cumulative_horizon",
    )


def _inventory(observed_at: datetime = datetime(2026, 1, 1, 5, tzinfo=UTC)) -> InventorySnapshot:
    return InventorySnapshot(
        store_id="S001",
        product_id="P001",
        observed_at=observed_at,
        mean_units=4.0,
        lower_units=3.0,
        upper_units=5.0,
        unit="unit",
        belief_version="b1",
    )


def _context() -> DecisionContext:
    return DecisionContext(
        forecast=_forecast(),
        inventory=_inventory(),
        pending_orders=(PendingOrder("o1", "S001", "P001", datetime(2026, 1, 2, tzinfo=UTC), 2.0, "unit"),),
        constraints=OrderingConstraints(case_pack=2),
        policy_version="p1",
        order_cutoff=datetime(2026, 1, 1, 6, tzinfo=UTC),
        review_period_days=1,
        lead_time_days=1,
        shelf_life_days=3,
        service_quantile=0.9,
    )


def test_horizon_mismatch_is_rejected() -> None:
    context = _context()
    bad = DecisionContext(**{**context.__dict__, "forecast": _forecast(horizon_days=1)})

    with pytest.raises(DecisionContractError, match="horizon"):
        validate_decision_context(bad)


def test_quantile_addition_without_dependence_is_rejected() -> None:
    with pytest.raises(DecisionContractError, match="cannot be added"):
        sum_marginal_quantiles_without_dependence()


def test_stale_inventory_is_rejected() -> None:
    context = _context()
    bad = DecisionContext(
        **{**context.__dict__, "inventory": _inventory(datetime(2026, 1, 1, 7, tzinfo=UTC))}
    )

    with pytest.raises(DecisionContractError, match="stale"):
        validate_decision_context(bad)


def test_duplicate_pending_orders_are_rejected() -> None:
    context = _context()
    duplicate = PendingOrder("o1", "S001", "P001", datetime(2026, 1, 2, tzinfo=UTC), 1.0, "unit")
    bad = DecisionContext(**{**context.__dict__, "pending_orders": (*context.pending_orders, duplicate)})

    with pytest.raises(DecisionContractError, match="Duplicate"):
        validate_decision_context(bad)


def test_unit_conversion_is_explicit() -> None:
    assert convert_units(2.0, from_unit="case", to_unit="unit", conversion={("case", "unit"): 6.0}) == 12.0


def test_cumulative_demand_from_scenarios_is_monotone_and_deterministic() -> None:
    marginals = pd.DataFrame({"q05": [1.0, 1.0], "q50": [3.0, 3.0], "q95": [10.0, 10.0]})

    first = generate_demand_scenarios(
        marginals,
        quantile_columns=("q05", "q50", "q95"),
        scenarios=20,
        seed=4,
        dependence="comonotonic",
    )
    second = generate_demand_scenarios(
        marginals,
        quantile_columns=("q05", "q50", "q95"),
        scenarios=20,
        seed=4,
        dependence="comonotonic",
    )
    cumulative = cumulative_quantiles_from_scenarios(first, quantiles=(0.05, 0.5, 0.95))

    pd.testing.assert_frame_equal(first, second)
    assert cumulative[0.05] <= cumulative[0.5] <= cumulative[0.95]


def test_recommendation_records_reproducible_inputs_and_binding_factors() -> None:
    recommendation = build_order_recommendation(_context())

    assert recommendation.recommended_quantity == 6
    assert recommendation.forecast_version == "m1"
    assert recommendation.inventory_belief_version == "b1"
    assert "case_pack" in recommendation.explanation["binding_factors"]
