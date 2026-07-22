"""Ordering policies for uncertain perishable demand."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PolicyContext:
    """State visible to an ordering policy at decision time."""

    forecast_target: float
    forecast_median: float
    observed_inventory: float
    pipeline_inventory: float
    lead_time_days: int
    shelf_life_days: int


class OrderingPolicy(Protocol):
    """Protocol implemented by all policies."""

    @property
    def name(self) -> str:
        """Return the stable policy identifier."""
        ...

    def order(self, context: PolicyContext) -> int:
        """Return a non-negative integer order quantity."""
        ...


@dataclass(frozen=True)
class QuantileBaseStockPolicy:
    """Order up to a quantile-derived inventory position."""

    name: str = "quantile_base_stock"
    lead_time_multiplier: float = 1.0

    def order(self, context: PolicyContext) -> int:
        """Use a service-level demand quantile as the order-up-to target."""
        protection_days = max(1.0, context.lead_time_days * self.lead_time_multiplier)
        target = context.forecast_target * protection_days
        inventory_position = context.observed_inventory + context.pipeline_inventory
        return max(0, round(target - inventory_position))


@dataclass(frozen=True)
class MedianPolicy:
    """Simple median-demand baseline."""

    name: str = "median_baseline"

    def order(self, context: PolicyContext) -> int:
        """Order up to median expected demand over lead time."""
        protection_days = max(1, context.lead_time_days)
        target = context.forecast_median * protection_days
        inventory_position = context.observed_inventory + context.pipeline_inventory
        return max(0, round(target - inventory_position))


@dataclass(frozen=True)
class ClairvoyantPolicy:
    """Lower-bound benchmark that knows next-day demand.

    This policy is not deployable. It is useful for measuring operational regret.
    """

    known_demand: int
    name: str = "clairvoyant_lower_bound"

    def order(self, context: PolicyContext) -> int:
        """Order exactly the known demand net of inventory position."""
        inventory_position = context.observed_inventory + context.pipeline_inventory
        return max(0, round(self.known_demand - inventory_position))


def critical_fractile(
    unit_margin: float,
    unit_cost: float,
    waste_cost: float,
) -> float:
    """Return the single-period newsvendor critical fractile.

    Underage cost is approximated by lost contribution margin. Overage cost
    includes procurement and disposal. The result is clipped away from the
    interval boundaries for numerical stability.
    """
    underage = max(unit_margin, 0.0)
    overage = max(unit_cost + waste_cost, 0.0)
    denominator = underage + overage
    if denominator <= 0.0:
        return 0.5
    return min(max(underage / denominator, 0.01), 0.99)
