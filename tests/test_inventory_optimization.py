from __future__ import annotations

from perishable_lab.inventory.optimization import (
    ExhaustiveEnumerationSolver,
    InventoryCostParameters,
    InventoryOptimizationProblem,
    age_structured_base_stock_order,
    newsvendor_order_with_service,
    sample_average_approximation,
    worst_case_robust_order,
)
from perishable_lab.inventory.policies import OrderingConstraints


def test_newsvendor_service_constraint_uses_higher_service_target() -> None:
    order = newsvendor_order_with_service(
        5.0,
        service_floor_quantile=8.0,
        observed_inventory=2.0,
        pipeline_inventory=1.0,
        constraints=OrderingConstraints(),
    )

    assert order == 5


def test_age_structured_base_stock_discounts_expiring_units() -> None:
    order = age_structured_base_stock_order(
        demand_target=10.0,
        usable_inventory_by_age=(4.0, 4.0),
        pipeline_inventory=0.0,
        expiring_stock_discount=1.0,
        constraints=OrderingConstraints(),
        lead_time_days=1,
        shelf_life_days=2,
    )

    assert order == 6


def test_sample_average_matches_exhaustive_tiny_problem() -> None:
    problem = InventoryOptimizationProblem(
        demand_scenarios=(2.0, 4.0),
        observed_inventory=0.0,
        constraints=OrderingConstraints(),
        costs=InventoryCostParameters(unit_cost=1.0, unit_margin=5.0, waste_cost=1.0),
        max_order_quantity=6,
    )

    result = sample_average_approximation(problem)
    exhaustive = ExhaustiveEnumerationSolver().solve(problem)

    assert result.status == "optimal"
    assert result.order_quantity == exhaustive.order_quantity


def test_case_pack_rounding_is_enforced() -> None:
    problem = InventoryOptimizationProblem(
        demand_scenarios=(5.0, 6.0),
        constraints=OrderingConstraints(case_pack=4),
        costs=InventoryCostParameters(unit_cost=1.0, unit_margin=10.0, waste_cost=1.0),
        max_order_quantity=10,
    )

    result = sample_average_approximation(problem)

    assert result.order_quantity % 4 == 0


def test_infeasible_service_constraint_is_reported() -> None:
    problem = InventoryOptimizationProblem(
        demand_scenarios=(100.0,),
        minimum_fill_rate=0.99,
        max_order_quantity=10,
    )

    result = sample_average_approximation(problem)

    assert result.status == "infeasible"
    assert result.fallback_reason == "no_feasible_quantity"


def test_higher_lost_margin_does_not_reduce_order() -> None:
    low = InventoryOptimizationProblem(
        demand_scenarios=(2.0, 8.0),
        costs=InventoryCostParameters(unit_cost=1.0, unit_margin=1.0, waste_cost=0.0),
        max_order_quantity=10,
    )
    high = InventoryOptimizationProblem(
        demand_scenarios=(2.0, 8.0),
        costs=InventoryCostParameters(unit_cost=1.0, unit_margin=10.0, waste_cost=0.0),
        max_order_quantity=10,
    )

    assert sample_average_approximation(high).order_quantity >= sample_average_approximation(low).order_quantity


def test_robust_order_is_at_least_expected_cost_order_under_tail_risk() -> None:
    problem = InventoryOptimizationProblem(
        demand_scenarios=(1.0, 10.0),
        costs=InventoryCostParameters(unit_cost=1.0, unit_margin=8.0, waste_cost=0.0),
        max_order_quantity=12,
    )

    assert worst_case_robust_order(problem).order_quantity >= sample_average_approximation(problem).order_quantity


def test_timeout_returns_deterministic_fallback() -> None:
    problem = InventoryOptimizationProblem(
        demand_scenarios=tuple(float(value) for value in range(50)),
        max_order_quantity=500,
    )

    result = sample_average_approximation(problem, timeout_seconds=0.0)

    assert result.status == "timeout"
    assert result.fallback_reason == "timeout"
