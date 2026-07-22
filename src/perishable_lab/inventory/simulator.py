"""Cohort-based simulator for perishable inventory."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd

from perishable_lab.inventory.policies import OrderingPolicy, PolicyContext


@dataclass
class InventoryState:
    """Mutable inventory state for one store-product series."""

    cohorts: deque[tuple[int, int]]
    pipeline: dict[int, int]

    @classmethod
    def empty(cls) -> InventoryState:
        """Construct an empty inventory state."""
        return cls(cohorts=deque(), pipeline={})

    @property
    def on_hand(self) -> int:
        """Return total physical stock across age cohorts."""
        return int(sum(quantity for quantity, _remaining_life in self.cohorts))

    @property
    def pipeline_inventory(self) -> int:
        """Return total ordered but not yet received stock."""
        return int(sum(self.pipeline.values()))


@dataclass(frozen=True)
class SimulationCosts:
    """Unit cost assumptions used in operational evaluation."""

    holding_cost_per_unit_day: float = 0.03


def _receive_arrivals(state: InventoryState, day_index: int, shelf_life_days: int) -> int:
    arrival = int(state.pipeline.pop(day_index, 0))
    if arrival > 0:
        state.cohorts.append((arrival, shelf_life_days))
    return arrival


def _age_and_expire(state: InventoryState) -> int:
    waste = 0
    next_cohorts: deque[tuple[int, int]] = deque()
    while state.cohorts:
        quantity, remaining_life = state.cohorts.popleft()
        aged_life = remaining_life - 1
        if aged_life <= 0:
            waste += quantity
        elif quantity > 0:
            next_cohorts.append((quantity, aged_life))
    state.cohorts = next_cohorts
    return waste


def _apply_shrinkage(
    state: InventoryState,
    rate: float,
    rng: np.random.Generator,
) -> int:
    total = state.on_hand
    if total <= 0 or rate <= 0.0:
        return 0
    lost = int(rng.binomial(total, min(max(rate, 0.0), 1.0)))
    remaining = lost
    updated: deque[tuple[int, int]] = deque()
    while state.cohorts:
        quantity, life = state.cohorts.popleft()
        removed = min(quantity, remaining)
        quantity -= removed
        remaining -= removed
        if quantity > 0:
            updated.append((quantity, life))
    state.cohorts = updated
    return lost


def _fulfil_fifo(state: InventoryState, demand: int) -> tuple[int, int]:
    remaining = max(0, int(demand))
    fulfilled = 0
    updated: deque[tuple[int, int]] = deque()
    while state.cohorts:
        quantity, life = state.cohorts.popleft()
        sold = min(quantity, remaining)
        quantity -= sold
        remaining -= sold
        fulfilled += sold
        if quantity > 0:
            updated.append((quantity, life))
    state.cohorts = updated
    return fulfilled, remaining


def simulate_series(
    frame: pd.DataFrame,
    policy: OrderingPolicy,
    *,
    service_forecast_column: str,
    median_forecast_column: str = "q50",
    costs: SimulationCosts | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate one ordered store-product time series.

    Required columns include demand, forecast columns, shelf life, lead time,
    unit economics, shrinkage, and inventory record error standard deviation.
    """
    required = {
        "date",
        "demand",
        service_forecast_column,
        median_forecast_column,
        "shelf_life_days",
        "lead_time_days",
        "unit_cost",
        "unit_margin",
        "waste_cost",
        "shrinkage_rate",
        "record_error_std",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Simulation frame is missing columns: {sorted(missing)}")

    ordered = frame.sort_values("date").reset_index(drop=True)
    effective_costs = costs or SimulationCosts()
    state = InventoryState.empty()
    rng = np.random.default_rng(seed)
    records: list[dict[str, object]] = []

    for day_index, (_index, row) in enumerate(ordered.iterrows()):
        shelf_life = int(row["shelf_life_days"])
        lead_time = int(row["lead_time_days"])
        expired = _age_and_expire(state)
        arrival = _receive_arrivals(state, day_index, shelf_life)
        shrinkage = _apply_shrinkage(state, float(row["shrinkage_rate"]), rng)

        fulfilled, lost_sales = _fulfil_fifo(state, int(row["demand"]))
        observed_error = rng.normal(0.0, float(row["record_error_std"]))
        observed_inventory = max(0.0, state.on_hand + observed_error)
        context = PolicyContext(
            forecast_target=float(row[service_forecast_column]),
            forecast_median=float(row[median_forecast_column]),
            observed_inventory=observed_inventory,
            pipeline_inventory=float(state.pipeline_inventory),
            lead_time_days=lead_time,
            shelf_life_days=shelf_life,
        )
        order_quantity = policy.order(context)
        arrival_day = day_index + max(1, lead_time)
        state.pipeline[arrival_day] = state.pipeline.get(arrival_day, 0) + order_quantity

        ending_inventory = state.on_hand
        waste = expired + shrinkage
        holding_cost = ending_inventory * effective_costs.holding_cost_per_unit_day
        waste_cost = waste * (float(row["unit_cost"]) + float(row["waste_cost"]))
        lost_sales_cost = lost_sales * float(row["unit_margin"])
        total_cost = holding_cost + waste_cost + lost_sales_cost

        records.append(
            {
                "date": row["date"],
                "demand": int(row["demand"]),
                "arrival": arrival,
                "order_quantity": order_quantity,
                "fulfilled": fulfilled,
                "lost_sales": lost_sales,
                "expired_units": expired,
                "shrinkage_units": shrinkage,
                "waste_units": waste,
                "ending_inventory": ending_inventory,
                "observed_inventory": observed_inventory,
                "pipeline_inventory": state.pipeline_inventory,
                "holding_cost": holding_cost,
                "waste_cost_total": waste_cost,
                "lost_sales_cost": lost_sales_cost,
                "total_cost": total_cost,
            }
        )

    return pd.DataFrame(records)


def summarise_simulation(frame: pd.DataFrame, policy_name: str) -> dict[str, float | str]:
    """Aggregate a daily simulation into operational KPIs."""
    demand = float(frame["demand"].sum())
    fulfilled = float(frame["fulfilled"].sum())
    ordered = float(frame["order_quantity"].sum())
    waste = float(frame["waste_units"].sum())
    lost_sales = float(frame["lost_sales"].sum())
    denominator = max(demand, 1.0)
    supply_denominator = max(ordered + float(frame["arrival"].iloc[0]), 1.0)
    return {
        "policy": policy_name,
        "demand_units": demand,
        "fulfilled_units": fulfilled,
        "ordered_units": ordered,
        "waste_units": waste,
        "lost_sales_units": lost_sales,
        "fill_rate": fulfilled / denominator,
        "lost_sales_rate": lost_sales / denominator,
        "waste_rate": waste / supply_denominator,
        "average_inventory": float(frame["ending_inventory"].mean()),
        "average_order_quantity": float(frame["order_quantity"].mean()),
        "total_cost": float(frame["total_cost"].sum()),
        "cost_per_demand_unit": float(frame["total_cost"].sum()) / denominator,
    }


def simulate_panel(
    frame: pd.DataFrame,
    policy: OrderingPolicy,
    *,
    service_forecast_column: str,
    seed: int = 42,
    costs: SimulationCosts | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate every store-product series and return daily and aggregate outputs."""
    daily_parts: list[pd.DataFrame] = []
    summaries: list[dict[str, float | str]] = []

    grouped = frame.groupby(["store_id", "product_id"], sort=False)
    for group_index, (group_key, group) in enumerate(grouped):
        store_id, product_id = (str(group_key[0]), str(group_key[1]))
        daily = simulate_series(
            group,
            policy,
            service_forecast_column=service_forecast_column,
            seed=seed + group_index,
            costs=costs,
        )
        daily.insert(0, "product_id", product_id)
        daily.insert(0, "store_id", store_id)
        daily_parts.append(daily)
        summary = summarise_simulation(daily, policy.name)
        summary.update({"store_id": store_id, "product_id": product_id})
        summaries.append(summary)

    return pd.concat(daily_parts, ignore_index=True), pd.DataFrame(summaries)
