"""Supplier lead-time and delivery-reliability modelling."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.inventory.simulator import SimulationControls


class SupplierReliabilityError(ValueError):
    """Raised when supplier delivery data are invalid."""


@dataclass(frozen=True)
class SupplierReliabilityDistribution:
    """Discrete lead-time and fulfilment distribution for a supplier lane."""

    supplier_id: str
    product_id: str
    support_lead_time_days: tuple[int, ...]
    lead_time_probabilities: tuple[float, ...]
    expected_fill_rate: float
    cancellation_probability: float
    rejection_probability: float
    source: str
    version: str
    sample_size: int

    def _lead_time_probabilities(self) -> NDArray[np.float64]:
        probabilities = np.asarray(self.lead_time_probabilities, dtype=float)
        normalised: NDArray[np.float64] = probabilities / probabilities.sum()
        return normalised

    def sample(self, n: int, *, seed: int) -> pd.DataFrame:
        """Sample deterministic delivery scenarios for replayable simulations."""
        if n < 1:
            raise ValueError("Sample size must be positive")
        rng = np.random.default_rng(seed)
        lead_times = rng.choice(
            np.asarray(self.support_lead_time_days, dtype=np.int64),
            size=n,
            replace=True,
            p=self._lead_time_probabilities(),
        )
        cancelled = rng.random(n) < self.cancellation_probability
        rejected = rng.random(n) < self.rejection_probability
        fill_rates = np.where(cancelled | rejected, 0.0, self.expected_fill_rate)
        return pd.DataFrame(
            {
                "scenario_id": range(n),
                "supplier_id": self.supplier_id,
                "product_id": self.product_id,
                "lead_time_days": lead_times.astype(int),
                "supplier_fill_rate": fill_rates.astype(float),
                "cancelled": cancelled,
                "rejected": rejected,
                "distribution_source": self.source,
                "supplier_reliability_version": self.version,
            }
        )


def add_valid_delivery_days(
    start_date: str | pd.Timestamp,
    lead_time_days: int,
    calendar: pd.DataFrame,
) -> pd.Timestamp:
    """Advance by valid delivery days, skipping closed dates in the calendar."""
    if lead_time_days < 0:
        raise ValueError("Lead time cannot be negative")
    required = {"date", "can_deliver"}
    missing = sorted(required.difference(calendar.columns))
    if missing:
        raise SupplierReliabilityError(f"Calendar is missing columns: {missing}")
    open_dates = {
        pd.Timestamp(row["date"]).normalize()
        for _, row in calendar.iterrows()
        if bool(row["can_deliver"])
    }
    current = pd.Timestamp(start_date).normalize()
    remaining = lead_time_days
    while remaining > 0:
        current += pd.Timedelta(days=1)
        if current in open_dates:
            remaining -= 1
    return current


def prepare_delivery_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate order-to-receipt events and derive reliability targets."""
    required = {
        "order_id",
        "supplier_id",
        "product_id",
        "created_at",
        "requested_delivery_date",
        "ordered_quantity",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SupplierReliabilityError(f"Delivery events are missing columns: {missing}")
    prepared = frame.copy(deep=True)
    for column in ("created_at", "acknowledged_at", "dispatch_at", "arrival_at", "receiving_completed_at"):
        if column in prepared.columns:
            prepared[column] = pd.to_datetime(prepared[column], utc=True)
    prepared["requested_delivery_date"] = pd.to_datetime(prepared["requested_delivery_date"]).dt.normalize()
    prepared["ordered_quantity"] = pd.to_numeric(prepared["ordered_quantity"], errors="coerce")
    prepared["accepted_quantity"] = pd.to_numeric(
        _column_or_default(prepared, "accepted_quantity", 0.0), errors="coerce"
    ).fillna(0.0)
    prepared["rejected_quantity"] = pd.to_numeric(
        _column_or_default(prepared, "rejected_quantity", 0.0), errors="coerce"
    ).fillna(0.0)
    prepared["cancelled"] = _column_or_default(prepared, "cancelled", False)
    prepared["cancelled"] = prepared["cancelled"].fillna(False).astype(bool)
    if bool((prepared["ordered_quantity"] < 0).any()):
        raise SupplierReliabilityError("Ordered quantity cannot be negative")
    arrival_date = prepared["arrival_at"].dt.tz_convert(None).dt.normalize()
    created_date = prepared["created_at"].dt.tz_convert(None).dt.normalize()
    prepared["actual_lead_time_days"] = (arrival_date - created_date).dt.days
    prepared.loc[prepared["cancelled"], "actual_lead_time_days"] = pd.NA
    prepared["fill_rate"] = (
        prepared["accepted_quantity"] / prepared["ordered_quantity"].clip(lower=1.0)
    ).clip(lower=0.0, upper=1.0)
    prepared.loc[prepared["cancelled"], "fill_rate"] = 0.0
    prepared["partial_fulfilment"] = (prepared["fill_rate"] < 1.0) & ~prepared["cancelled"]
    prepared["rejected_delivery"] = prepared["rejected_quantity"] > 0
    prepared["late_delivery"] = arrival_date > prepared["requested_delivery_date"]
    return prepared.sort_values(["created_at", "supplier_id", "product_id", "order_id"]).reset_index(drop=True)


@dataclass(frozen=True)
class ContractualLeadTimeModel:
    """Deterministic contractual supplier baseline."""

    lead_time_days: int
    fill_rate: float = 1.0
    version: str = "contractual:v1"

    def distribution_for(self, supplier_id: str, product_id: str) -> SupplierReliabilityDistribution:
        return SupplierReliabilityDistribution(
            supplier_id=supplier_id,
            product_id=product_id,
            support_lead_time_days=(self.lead_time_days,),
            lead_time_probabilities=(1.0,),
            expected_fill_rate=self.fill_rate,
            cancellation_probability=0.0,
            rejection_probability=0.0,
            source="contractual",
            version=self.version,
            sample_size=0,
        )


@dataclass(frozen=True)
class EmpiricalLeadTimeModel:
    """Empirical supplier-product lead-time and fill-rate model with fallback."""

    events: pd.DataFrame
    fallback: ContractualLeadTimeModel
    min_samples: int = 3
    version: str = "empirical:v1"

    @classmethod
    def fit(
        cls,
        events: pd.DataFrame,
        *,
        fallback: ContractualLeadTimeModel,
        min_samples: int = 3,
        version: str = "empirical:v1",
    ) -> EmpiricalLeadTimeModel:
        if min_samples < 1:
            raise ValueError("Minimum samples must be positive")
        return cls(prepare_delivery_events(events), fallback, min_samples, version)

    def distribution_for(self, supplier_id: str, product_id: str) -> SupplierReliabilityDistribution:
        lane = self.events[
            (self.events["supplier_id"] == supplier_id) & (self.events["product_id"] == product_id)
        ]
        completed = lane[~lane["cancelled"] & lane["actual_lead_time_days"].notna()]
        if int(completed.shape[0]) < self.min_samples:
            base = self.fallback.distribution_for(supplier_id, product_id)
            return SupplierReliabilityDistribution(
                supplier_id=supplier_id,
                product_id=product_id,
                support_lead_time_days=base.support_lead_time_days,
                lead_time_probabilities=base.lead_time_probabilities,
                expected_fill_rate=base.expected_fill_rate,
                cancellation_probability=base.cancellation_probability,
                rejection_probability=base.rejection_probability,
                source="fallback_contractual",
                version=base.version,
                sample_size=int(completed.shape[0]),
            )
        counts = completed["actual_lead_time_days"].astype(int).value_counts().sort_index()
        return SupplierReliabilityDistribution(
            supplier_id=supplier_id,
            product_id=product_id,
            support_lead_time_days=tuple(int(index) for index in counts.index),
            lead_time_probabilities=tuple(float(value) for value in counts.to_numpy()),
            expected_fill_rate=float(completed["fill_rate"].mean()),
            cancellation_probability=float(lane["cancelled"].mean()),
            rejection_probability=float(lane["rejected_delivery"].mean()),
            source="empirical_supplier_product",
            version=self.version,
            sample_size=int(completed.shape[0]),
        )


def simulation_controls_from_scenario(scenario: pd.Series) -> SimulationControls:
    """Convert one supplier scenario to simulator controls."""
    return SimulationControls(
        supplier_fill_rate=float(scenario["supplier_fill_rate"]),
        lead_time_jitter_probability=0.0,
        max_lead_time_jitter_days=0,
    )


def protect_random_lead_time_demand(
    daily_forecast: pd.Series,
    scenarios: pd.DataFrame,
    *,
    quantile: float = 0.9,
) -> float:
    """Return robust demand protection over sampled lead-time horizons."""
    demand = pd.to_numeric(daily_forecast, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    totals: list[float] = []
    for _, scenario in scenarios.iterrows():
        horizon = max(1, int(scenario["lead_time_days"]))
        totals.append(float(demand[:horizon].sum()))
    return float(np.quantile(np.asarray(totals, dtype=float), quantile))


def detect_supplier_shock(
    events: pd.DataFrame,
    *,
    window: int = 5,
    minimum_fill_rate: float = 0.8,
    maximum_late_rate: float = 0.5,
) -> pd.DataFrame:
    """Detect persistent supplier deterioration by lane."""
    prepared = prepare_delivery_events(events)
    rows: list[dict[str, object]] = []
    for keys, group in prepared.groupby(["supplier_id", "product_id"], sort=True):
        supplier_id, product_id = keys
        recent = pd.DataFrame(group).tail(window)
        fill_rate = float(recent["fill_rate"].mean()) if not recent.empty else 1.0
        late_rate = float(recent["late_delivery"].mean()) if not recent.empty else 0.0
        triggered = fill_rate < minimum_fill_rate or late_rate > maximum_late_rate
        rows.append(
            {
                "supplier_id": supplier_id,
                "product_id": product_id,
                "recent_orders": int(recent.shape[0]),
                "recent_fill_rate": fill_rate,
                "recent_late_rate": late_rate,
                "fallback_required": triggered,
                "reason": "supplier_shock" if triggered else "within_threshold",
            }
        )
    return pd.DataFrame(rows).sort_values(["supplier_id", "product_id"], ignore_index=True)


def supplier_distribution_manifest(distribution: SupplierReliabilityDistribution) -> dict[str, object]:
    """Return recommendation metadata for lead-time assumptions."""
    return asdict(distribution)


def _column_or_default(frame: pd.DataFrame, column: str, default: object) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)
