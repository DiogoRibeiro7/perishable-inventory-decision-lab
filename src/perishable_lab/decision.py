"""Decision-compatible forecast and recommendation contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd

from perishable_lab.inventory.policies import OrderingConstraints, PolicyContext


class DecisionContractError(ValueError):
    """Raised when forecast, state, or policy inputs are incompatible."""


@dataclass(frozen=True)
class ForecastDistribution:
    """Versioned forecast distribution with explicit horizon and unit semantics."""

    forecast_id: str
    product_id: str
    store_id: str
    generated_at: datetime
    target_start: datetime
    horizon_days: int
    unit: str
    quantiles: dict[float, float]
    model_version: str
    distribution_kind: Literal["marginal_daily", "cumulative_horizon", "scenario_paths"]


@dataclass(frozen=True)
class InventorySnapshot:
    """Inventory belief snapshot available at decision time."""

    store_id: str
    product_id: str
    observed_at: datetime
    mean_units: float
    lower_units: float
    upper_units: float
    unit: str
    belief_version: str


@dataclass(frozen=True)
class PendingOrder:
    """Versioned pending order used in inventory position."""

    order_id: str
    store_id: str
    product_id: str
    expected_arrival: datetime
    quantity: float
    unit: str


@dataclass(frozen=True)
class DecisionContext:
    """Complete persisted input set for one order recommendation."""

    forecast: ForecastDistribution
    inventory: InventorySnapshot
    pending_orders: tuple[PendingOrder, ...]
    constraints: OrderingConstraints
    policy_version: str
    order_cutoff: datetime
    review_period_days: int
    lead_time_days: int
    shelf_life_days: int
    service_quantile: float


@dataclass(frozen=True)
class OrderRecommendation:
    """Auditable order recommendation."""

    store_id: str
    product_id: str
    recommended_quantity: int
    unit: str
    policy_version: str
    forecast_id: str
    forecast_version: str
    inventory_belief_version: str
    explanation: dict[str, object]


def generate_demand_scenarios(
    daily_marginal_quantiles: pd.DataFrame,
    *,
    quantile_columns: tuple[str, ...],
    scenarios: int,
    seed: int,
    dependence: Literal["independent", "comonotonic"],
) -> pd.DataFrame:
    """Generate deterministic demand scenario paths from marginal quantile curves."""
    if scenarios < 1:
        raise ValueError("Scenario count must be positive")
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    quantile_levels = np.asarray([float(column.removeprefix("q")) / 100.0 for column in quantile_columns])
    for scenario_id in range(scenarios):
        shared_u = rng.random()
        for horizon_index, row in daily_marginal_quantiles.reset_index(drop=True).iterrows():
            u = shared_u if dependence == "comonotonic" else rng.random()
            values = row[list(quantile_columns)].to_numpy(dtype=float)
            demand = float(np.interp(u, quantile_levels, values))
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "horizon_index": horizon_index,
                    "demand": max(0.0, demand),
                }
            )
    return pd.DataFrame(rows)


def cumulative_quantiles_from_scenarios(
    scenario_paths: pd.DataFrame,
    *,
    quantiles: tuple[float, ...],
) -> dict[float, float]:
    """Convert demand scenario paths into monotone cumulative horizon quantiles."""
    totals = scenario_paths.groupby("scenario_id")["demand"].sum()
    values = np.maximum.accumulate([float(totals.quantile(quantile)) for quantile in quantiles])
    return {quantile: value for quantile, value in zip(quantiles, values, strict=True)}


def sum_marginal_quantiles_without_dependence() -> None:
    """Reject invalid direct addition of marginal daily quantiles."""
    raise DecisionContractError(
        "Marginal daily quantiles cannot be added without a dependence model or scenario paths"
    )


def convert_units(value: float, *, from_unit: str, to_unit: str, conversion: dict[tuple[str, str], float]) -> float:
    """Convert units only through an explicit conversion map."""
    if from_unit == to_unit:
        return value
    return value * conversion[(from_unit, to_unit)]


def validate_decision_context(
    context: DecisionContext,
    *,
    expected_unit: str = "unit",
) -> None:
    """Validate horizon, unit, identity, timestamp, and pending-order contracts."""
    forecast = context.forecast
    inventory = context.inventory
    if forecast.store_id != inventory.store_id or forecast.product_id != inventory.product_id:
        raise DecisionContractError("Forecast and inventory identity do not match")
    if forecast.unit != expected_unit or inventory.unit != expected_unit:
        raise DecisionContractError("Forecast and inventory units are incompatible")
    expected_horizon = context.review_period_days + context.lead_time_days
    if forecast.horizon_days != expected_horizon:
        raise DecisionContractError("Forecast horizon does not match protection horizon")
    if inventory.observed_at > context.order_cutoff:
        raise DecisionContractError("Inventory snapshot is stale relative to order cutoff")
    order_ids = [order.order_id for order in context.pending_orders]
    if len(order_ids) != len(set(order_ids)):
        raise DecisionContractError("Duplicate pending orders are not allowed")
    for order in context.pending_orders:
        if order.store_id != forecast.store_id or order.product_id != forecast.product_id:
            raise DecisionContractError("Pending order identity does not match recommendation context")
        if order.unit != expected_unit:
            raise DecisionContractError("Pending order unit is incompatible")
    if not context.policy_version:
        raise DecisionContractError("Policy version is required")
    if forecast.distribution_kind != "cumulative_horizon":
        raise DecisionContractError("Policy input requires a cumulative horizon distribution")


def build_order_recommendation(context: DecisionContext) -> OrderRecommendation:
    """Convert a compatible cumulative forecast into a reproducible recommendation."""
    validate_decision_context(context)
    service_target = context.forecast.quantiles[context.service_quantile]
    pipeline_inventory = sum(order.quantity for order in context.pending_orders)
    policy_context = PolicyContext(
        forecast_target=service_target,
        forecast_median=context.forecast.quantiles.get(0.5, service_target),
        observed_inventory=context.inventory.lower_units,
        pipeline_inventory=pipeline_inventory,
        lead_time_days=context.lead_time_days,
        shelf_life_days=context.shelf_life_days,
    )
    requested = round(service_target - context.inventory.lower_units - pipeline_inventory)
    quantity = max(0, requested)
    from perishable_lab.inventory.policies import apply_ordering_constraints

    quantity = apply_ordering_constraints(quantity, policy_context, context.constraints)
    explanation = {
        "forecast": asdict(context.forecast),
        "inventory": asdict(context.inventory),
        "pending_orders": [asdict(order) for order in context.pending_orders],
        "constraints": asdict(context.constraints),
        "binding_factors": _binding_factors(requested, quantity, context.constraints),
        "protection_horizon_days": context.review_period_days + context.lead_time_days,
    }
    return OrderRecommendation(
        store_id=context.forecast.store_id,
        product_id=context.forecast.product_id,
        recommended_quantity=quantity,
        unit=context.forecast.unit,
        policy_version=context.policy_version,
        forecast_id=context.forecast.forecast_id,
        forecast_version=context.forecast.model_version,
        inventory_belief_version=context.inventory.belief_version,
        explanation=explanation,
    )


def _binding_factors(requested: int, quantity: int, constraints: OrderingConstraints) -> list[str]:
    factors: list[str] = []
    if constraints.case_pack > 1 and quantity % constraints.case_pack == 0 and quantity != requested:
        factors.append("case_pack")
    if constraints.minimum_order_quantity and 0 < quantity < constraints.minimum_order_quantity:
        factors.append("minimum_order_quantity")
    if constraints.storage_capacity_units is not None and quantity < requested:
        factors.append("storage_capacity")
    if not factors:
        factors.append("none")
    return factors
