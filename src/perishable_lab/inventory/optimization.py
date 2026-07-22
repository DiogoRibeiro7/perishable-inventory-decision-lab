"""Solver-independent stochastic and robust inventory optimisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal, Protocol

import numpy as np
import pandas as pd

from perishable_lab.inventory.policies import (
    OrderingConstraints,
    PolicyContext,
    apply_ordering_constraints,
)


@dataclass(frozen=True)
class InventoryCostParameters:
    """Economic cost parameters for order optimisation."""

    unit_cost: float
    unit_margin: float
    waste_cost: float
    holding_cost: float = 0.0
    service_penalty: float = 0.0


@dataclass(frozen=True)
class InventoryOptimizationProblem:
    """Single decision problem with scenarios and hard constraints."""

    demand_scenarios: tuple[float, ...]
    lead_time_scenarios: tuple[int, ...] = (1,)
    shelf_life_scenarios: tuple[int, ...] = (3,)
    observed_inventory: float = 0.0
    pipeline_inventory: float = 0.0
    constraints: OrderingConstraints = field(default_factory=OrderingConstraints)
    costs: InventoryCostParameters = field(
        default_factory=lambda: InventoryCostParameters(
            unit_cost=1.0,
            unit_margin=1.0,
            waste_cost=0.0,
        )
    )
    minimum_fill_rate: float | None = None
    maximum_stockout_risk: float | None = None
    max_order_quantity: int = 100


@dataclass(frozen=True)
class OptimizationResult:
    """Auditable optimisation result."""

    order_quantity: int
    objective_value: float
    solver: str
    solver_version: str
    status: Literal["optimal", "feasible_fallback", "infeasible", "timeout"]
    optimality_gap: float | None
    runtime_seconds: float
    fallback_reason: str | None = None


class InventorySolver(Protocol):
    """Solver-independent optimisation interface."""

    name: str

    def solve(self, problem: InventoryOptimizationProblem, *, timeout_seconds: float | None = None) -> OptimizationResult:
        """Solve an inventory optimisation problem."""


def newsvendor_order_with_service(
    demand_quantile: float,
    *,
    service_floor_quantile: float,
    observed_inventory: float,
    pipeline_inventory: float,
    constraints: OrderingConstraints,
    lead_time_days: int = 1,
    shelf_life_days: int = 1,
) -> int:
    """Single-period newsvendor order with a service floor."""
    target = max(demand_quantile, service_floor_quantile)
    context = PolicyContext(
        forecast_target=target,
        forecast_median=target,
        observed_inventory=observed_inventory,
        pipeline_inventory=pipeline_inventory,
        lead_time_days=lead_time_days,
        shelf_life_days=shelf_life_days,
    )
    requested = round(target - observed_inventory - pipeline_inventory)
    return apply_ordering_constraints(requested, context, constraints)


def age_structured_base_stock_order(
    *,
    demand_target: float,
    usable_inventory_by_age: tuple[float, ...],
    pipeline_inventory: float,
    expiring_stock_discount: float,
    constraints: OrderingConstraints,
    lead_time_days: int,
    shelf_life_days: int,
) -> int:
    """Multi-period age-structured base-stock approximation."""
    usable = 0.0
    for age_index, quantity in enumerate(usable_inventory_by_age):
        remaining_life = max(0, shelf_life_days - age_index)
        discount = expiring_stock_discount if remaining_life <= lead_time_days else 0.0
        usable += max(0.0, quantity * (1.0 - discount))
    context = PolicyContext(
        forecast_target=demand_target,
        forecast_median=demand_target,
        observed_inventory=usable,
        pipeline_inventory=pipeline_inventory,
        lead_time_days=lead_time_days,
        shelf_life_days=shelf_life_days,
    )
    return apply_ordering_constraints(
        round(demand_target - usable - pipeline_inventory),
        context,
        constraints,
    )


def _scenario_cost(order_quantity: int, problem: InventoryOptimizationProblem, demand: float) -> float:
    available = problem.observed_inventory + problem.pipeline_inventory + order_quantity
    fulfilled = min(available, demand)
    lost_sales = max(0.0, demand - fulfilled)
    ending = max(0.0, available - demand)
    waste = max(0.0, ending - max(problem.shelf_life_scenarios))
    return float(
        order_quantity * problem.costs.unit_cost
        + lost_sales * (problem.costs.unit_margin + problem.costs.service_penalty)
        + ending * problem.costs.holding_cost
        + waste * problem.costs.waste_cost
    )


def _feasible_order_quantities(problem: InventoryOptimizationProblem) -> list[int]:
    quantities: list[int] = []
    for quantity in range(0, problem.max_order_quantity + 1):
        context = PolicyContext(
            forecast_target=float(quantity),
            forecast_median=float(quantity),
            observed_inventory=problem.observed_inventory,
            pipeline_inventory=problem.pipeline_inventory,
            lead_time_days=max(problem.lead_time_scenarios),
            shelf_life_days=max(problem.shelf_life_scenarios),
        )
        constrained = apply_ordering_constraints(quantity, context, problem.constraints)
        if constrained == quantity:
            quantities.append(quantity)
    return quantities


def _constraint_satisfied(problem: InventoryOptimizationProblem, order_quantity: int) -> bool:
    demand = np.asarray(problem.demand_scenarios, dtype=float)
    available = problem.observed_inventory + problem.pipeline_inventory + order_quantity
    fill_rates = np.minimum(available, demand) / np.maximum(demand, 1e-9)
    stockout_risk = float(np.mean(available < demand))
    if problem.minimum_fill_rate is not None and float(np.mean(fill_rates)) < problem.minimum_fill_rate:
        return False
    return not (
        problem.maximum_stockout_risk is not None
        and stockout_risk > problem.maximum_stockout_risk
    )


@dataclass(frozen=True)
class ExhaustiveEnumerationSolver:
    """Deterministic open fallback for small scenario problems."""

    robust: bool = False
    name: str = "exhaustive_enumeration"
    version: str = "v1"

    def solve(self, problem: InventoryOptimizationProblem, *, timeout_seconds: float | None = None) -> OptimizationResult:
        start = perf_counter()
        best_quantity: int | None = None
        best_objective = float("inf")
        feasible = _feasible_order_quantities(problem)
        for quantity in feasible:
            if timeout_seconds is not None and perf_counter() - start > timeout_seconds:
                return _heuristic_fallback(problem, start, "timeout")
            if not _constraint_satisfied(problem, quantity):
                continue
            costs = [_scenario_cost(quantity, problem, demand) for demand in problem.demand_scenarios]
            objective = max(costs) if self.robust else float(np.mean(costs))
            if objective < best_objective:
                best_quantity = quantity
                best_objective = objective
        if best_quantity is None:
            return OptimizationResult(
                order_quantity=0,
                objective_value=float("inf"),
                solver=self.name,
                solver_version=self.version,
                status="infeasible",
                optimality_gap=None,
                runtime_seconds=perf_counter() - start,
                fallback_reason="no_feasible_quantity",
            )
        return OptimizationResult(
            order_quantity=best_quantity,
            objective_value=best_objective,
            solver=self.name,
            solver_version=self.version,
            status="optimal",
            optimality_gap=0.0,
            runtime_seconds=perf_counter() - start,
        )


def _heuristic_fallback(
    problem: InventoryOptimizationProblem,
    start: float,
    reason: str,
) -> OptimizationResult:
    target = float(np.quantile(np.asarray(problem.demand_scenarios, dtype=float), 0.9))
    context = PolicyContext(
        forecast_target=target,
        forecast_median=target,
        observed_inventory=problem.observed_inventory,
        pipeline_inventory=problem.pipeline_inventory,
        lead_time_days=max(problem.lead_time_scenarios),
        shelf_life_days=max(problem.shelf_life_scenarios),
    )
    quantity = apply_ordering_constraints(
        round(target - problem.observed_inventory - problem.pipeline_inventory),
        context,
        problem.constraints,
    )
    return OptimizationResult(
        order_quantity=quantity,
        objective_value=float("nan"),
        solver="deterministic_heuristic",
        solver_version="v1",
        status="timeout" if reason == "timeout" else "feasible_fallback",
        optimality_gap=None,
        runtime_seconds=perf_counter() - start,
        fallback_reason=reason,
    )


def sample_average_approximation(
    problem: InventoryOptimizationProblem,
    *,
    timeout_seconds: float | None = None,
) -> OptimizationResult:
    """Minimise expected scenario cost through deterministic enumeration."""
    return ExhaustiveEnumerationSolver(robust=False).solve(problem, timeout_seconds=timeout_seconds)


def worst_case_robust_order(
    problem: InventoryOptimizationProblem,
    *,
    timeout_seconds: float | None = None,
) -> OptimizationResult:
    """Minimise worst-case scenario cost over the uncertainty set."""
    return ExhaustiveEnumerationSolver(robust=True).solve(problem, timeout_seconds=timeout_seconds)


def compare_optimization_runs(results: list[OptimizationResult]) -> pd.DataFrame:
    """Return a deterministic comparison table for optimisation runs."""
    return pd.DataFrame([result.__dict__ for result in results]).sort_values(
        ["objective_value", "order_quantity"], ignore_index=True
    )
