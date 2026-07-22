"""Ordering policies for uncertain perishable demand."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
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
    expiring_inventory: float = 0.0


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
class OrderingConstraints:
    """Hard constraints applied to a requested replenishment quantity."""

    case_pack: int = 1
    minimum_order_quantity: int = 0
    storage_capacity_units: int | None = None
    display_minimum_units: int = 0

    def __post_init__(self) -> None:
        if self.case_pack < 1:
            raise ValueError("Case pack must be at least one")
        if self.minimum_order_quantity < 0:
            raise ValueError("Minimum order quantity cannot be negative")
        if self.storage_capacity_units is not None and self.storage_capacity_units < 0:
            raise ValueError("Storage capacity cannot be negative")
        if self.display_minimum_units < 0:
            raise ValueError("Display minimum cannot be negative")


def apply_ordering_constraints(
    requested_quantity: int,
    context: PolicyContext,
    constraints: OrderingConstraints,
) -> int:
    """Apply non-negativity, display, pack-size, minimum, and capacity constraints."""
    quantity = max(0, int(requested_quantity))
    projected_position = context.observed_inventory + context.pipeline_inventory + quantity
    display_gap = max(0, ceil(constraints.display_minimum_units - projected_position))
    quantity = max(quantity, display_gap)

    if quantity > 0 and constraints.minimum_order_quantity > 0:
        quantity = max(quantity, constraints.minimum_order_quantity)
    if constraints.case_pack > 1 and quantity > 0:
        quantity = ceil(quantity / constraints.case_pack) * constraints.case_pack

    if constraints.storage_capacity_units is None:
        return max(0, quantity)

    available_capacity = max(
        0,
        floor(
            constraints.storage_capacity_units
            - context.observed_inventory
            - context.pipeline_inventory
        ),
    )
    quantity = min(quantity, available_capacity)
    if constraints.case_pack > 1:
        quantity = floor(quantity / constraints.case_pack) * constraints.case_pack
    if 0 < quantity < constraints.minimum_order_quantity:
        return 0
    return max(0, quantity)


@dataclass(frozen=True)
class ConstrainedBaseStockPolicy:
    """Order up to a service target while enforcing operational hard constraints."""

    constraints: OrderingConstraints = OrderingConstraints()
    name: str = "constrained_base_stock"
    lead_time_multiplier: float = 1.0

    def order(self, context: PolicyContext) -> int:
        """Return a constrained order quantity."""
        protection_days = max(1.0, context.lead_time_days * self.lead_time_multiplier)
        target = context.forecast_target * protection_days
        inventory_position = context.observed_inventory + context.pipeline_inventory
        requested = round(target - inventory_position)
        return apply_ordering_constraints(requested, context, self.constraints)


@dataclass(frozen=True)
class AgeAwareBaseStockPolicy:
    """Discount stock likely to expire before it can satisfy future demand."""

    name: str = "age_aware_base_stock"
    expiring_stock_discount: float = 1.0

    def order(self, context: PolicyContext) -> int:
        """Order against usable inventory after discounting expiring stock."""
        discount = min(max(self.expiring_stock_discount, 0.0), 1.0)
        usable_inventory = max(0.0, context.observed_inventory - discount * context.expiring_inventory)
        protection_days = max(1, context.lead_time_days)
        target = context.forecast_target * protection_days
        inventory_position = usable_inventory + context.pipeline_inventory
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
