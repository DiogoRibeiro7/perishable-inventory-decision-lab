"""Inventory ledger reconciliation and hidden-state belief utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from perishable_lab.inventory.policies import PolicyContext


@dataclass(frozen=True)
class InventoryBelief:
    """Probabilistic belief about physical inventory."""

    store_id: str
    product_id: str
    mean_units: float
    lower_units: float
    upper_units: float
    stockout_probability: float
    uncertainty_units: float
    source: str
    version: str


@dataclass(frozen=True)
class ReconciliationIssue:
    """Inventory reconciliation issue requiring review or fallback."""

    rule_id: str
    severity: str
    store_id: str
    product_id: str
    event_id: str
    message: str


def prepare_inventory_events(events: pd.DataFrame) -> pd.DataFrame:
    """Validate event-sourced inventory records and keep latest revisions."""
    required = {
        "event_id",
        "event_type",
        "event_time",
        "processing_time",
        "revision",
        "store_id",
        "product_id",
        "quantity",
    }
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"Inventory events are missing columns: {missing}")
    prepared = events.copy(deep=True)
    prepared["event_time"] = pd.to_datetime(prepared["event_time"], utc=True)
    prepared["processing_time"] = pd.to_datetime(prepared["processing_time"], utc=True)
    prepared["revision"] = prepared["revision"].astype(int)
    prepared["quantity"] = pd.to_numeric(prepared["quantity"], errors="coerce")
    if bool(prepared["quantity"].isna().any()):
        raise ValueError("Inventory event quantity must be numeric")
    return (
        prepared.sort_values(["event_id", "revision", "processing_time"])
        .drop_duplicates("event_id", keep="last")
        .sort_values(["event_time", "processing_time", "event_id"])
        .reset_index(drop=True)
    )


def _event_delta(event_type: str, quantity: float, current_stock: float) -> float:
    if event_type in {"delivery", "return", "transfer_in"}:
        return quantity
    if event_type in {"sale", "transfer_out", "waste", "expiry", "shrinkage"}:
        return -quantity
    if event_type == "adjustment":
        return quantity
    if event_type == "count":
        return quantity - current_stock
    raise ValueError(f"Unsupported inventory event type: {event_type}")


def replay_stock_ledger(
    events: pd.DataFrame,
    *,
    initial_stock: float = 0.0,
    version: str = "ledger:v1",
) -> pd.DataFrame:
    """Replay inventory events into a deterministic reconstructed ledger."""
    prepared = prepare_inventory_events(events)
    rows: list[dict[str, object]] = []
    stock_by_key: dict[tuple[str, str], float] = {}
    for _, row in prepared.iterrows():
        key = (str(row["store_id"]), str(row["product_id"]))
        opening_stock = stock_by_key.get(key, initial_stock)
        delta = _event_delta(str(row["event_type"]), float(row["quantity"]), opening_stock)
        closing_stock = opening_stock + delta
        stock_by_key[key] = closing_stock
        rows.append(
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "event_time": row["event_time"],
                "processing_time": row["processing_time"],
                "revision": row["revision"],
                "store_id": row["store_id"],
                "product_id": row["product_id"],
                "quantity": float(row["quantity"]),
                "opening_reconstructed_stock": opening_stock,
                "stock_delta": delta,
                "closing_reconstructed_stock": closing_stock,
                "ledger_version": version,
            }
        )
    return pd.DataFrame(rows)


def build_reconciliation_report(
    events: pd.DataFrame,
    ledger: pd.DataFrame,
    *,
    positive_jump_threshold: float = 25.0,
    count_discrepancy_threshold: float = 10.0,
) -> pd.DataFrame:
    """Identify impossible ledgers, duplicate source IDs, late revisions, and count conflicts."""
    raw_duplicates = events.duplicated(["event_id"], keep=False)
    issues: list[ReconciliationIssue] = []
    if bool(raw_duplicates.any()):
        for _, row in events.loc[raw_duplicates].iterrows():
            issues.append(
                ReconciliationIssue(
                    "duplicate_event_revision",
                    "warning",
                    str(row["store_id"]),
                    str(row["product_id"]),
                    str(row["event_id"]),
                    "Multiple revisions exist for the same event ID.",
                )
            )
    raw = events.copy(deep=True)
    raw["event_time"] = pd.to_datetime(raw["event_time"], utc=True)
    raw["processing_time"] = pd.to_datetime(raw["processing_time"], utc=True)
    late = raw["processing_time"] > raw["event_time"] + pd.Timedelta(days=1)
    for _, row in raw.loc[late].iterrows():
        issues.append(
            ReconciliationIssue(
                "late_inventory_revision",
                "warning",
                str(row["store_id"]),
                str(row["product_id"]),
                str(row["event_id"]),
                "Processing time arrived after the replay window.",
            )
        )
    negative = ledger["closing_reconstructed_stock"] < 0
    for _, row in ledger.loc[negative].iterrows():
        issues.append(
            ReconciliationIssue(
                "negative_reconstructed_stock",
                "blocking",
                str(row["store_id"]),
                str(row["product_id"]),
                str(row["event_id"]),
                "Reconstructed stock became negative.",
            )
        )
    positive_jump = ledger["stock_delta"] > positive_jump_threshold
    for _, row in ledger.loc[positive_jump].iterrows():
        issues.append(
            ReconciliationIssue(
                "unexplained_positive_jump",
                "warning",
                str(row["store_id"]),
                str(row["product_id"]),
                str(row["event_id"]),
                "Positive stock jump requires delivery, return, transfer, or adjustment evidence.",
            )
        )
    count_rows = ledger[ledger["event_type"] == "count"]
    discrepancies = count_rows["stock_delta"].abs() > count_discrepancy_threshold
    for _, row in count_rows.loc[discrepancies].iterrows():
        issues.append(
            ReconciliationIssue(
                "contradictory_count",
                "review",
                str(row["store_id"]),
                str(row["product_id"]),
                str(row["event_id"]),
                "Physical count differs materially from reconstructed ledger.",
            )
        )
    if not issues:
        return pd.DataFrame(columns=["rule_id", "severity", "store_id", "product_id", "event_id", "message"])
    return pd.DataFrame([asdict(issue) for issue in issues]).sort_values(
        ["severity", "rule_id", "event_id"], ignore_index=True
    )


@dataclass(frozen=True)
class ParticleInventoryEstimator:
    """Small particle-filter prototype for hidden physical stock."""

    particles: int = 500
    process_noise_std: float = 1.0
    count_error_std: float = 1.0
    seed: int = 42
    version: str = "particle:v1"

    def initial_particles(self, initial_stock: float) -> NDArray[np.float64]:
        rng = np.random.default_rng(self.seed)
        return np.maximum(0.0, rng.normal(initial_stock, self.count_error_std, self.particles))

    def predict(self, particles: NDArray[np.float64], *, delta: float) -> NDArray[np.float64]:
        rng = np.random.default_rng(self.seed + len(particles) + int(abs(delta) * 100))
        predicted = particles + delta + rng.normal(0.0, self.process_noise_std, len(particles))
        return np.maximum(0.0, predicted)

    def update_with_count(
        self,
        particles: NDArray[np.float64],
        *,
        counted_units: float,
        trust: float = 1.0,
    ) -> NDArray[np.float64]:
        trust_weight = min(max(trust, 0.0), 1.0)
        return np.maximum(0.0, (1.0 - trust_weight) * particles + trust_weight * counted_units)

    def belief(self, store_id: str, product_id: str, particles: NDArray[np.float64]) -> InventoryBelief:
        return InventoryBelief(
            store_id=store_id,
            product_id=product_id,
            mean_units=float(np.mean(particles)),
            lower_units=float(np.quantile(particles, 0.05)),
            upper_units=float(np.quantile(particles, 0.95)),
            stockout_probability=float(np.mean(particles <= 0.5)),
            uncertainty_units=float(np.std(particles)),
            source="particle_filter",
            version=self.version,
        )


def conservative_interval_belief(
    *,
    store_id: str,
    product_id: str,
    recorded_units: float,
    uncertainty_units: float,
    version: str = "interval:v1",
) -> InventoryBelief:
    """Build a conservative interval state when evidence is insufficient."""
    lower = max(0.0, recorded_units - uncertainty_units)
    upper = max(lower, recorded_units + uncertainty_units)
    return InventoryBelief(
        store_id=store_id,
        product_id=product_id,
        mean_units=recorded_units,
        lower_units=lower,
        upper_units=upper,
        stockout_probability=1.0 if lower <= 0.0 and recorded_units <= uncertainty_units else 0.0,
        uncertainty_units=uncertainty_units,
        source="conservative_interval",
        version=version,
    )


def policy_context_from_belief(
    belief: InventoryBelief,
    *,
    forecast_target: float,
    forecast_median: float,
    pipeline_inventory: float,
    uncertainty_threshold: float,
    lead_time_days: int = 1,
    shelf_life_days: int = 1,
) -> PolicyContext:
    """Expose conservative inventory to policies when uncertainty is high."""
    observed_inventory = belief.mean_units
    if belief.uncertainty_units > uncertainty_threshold:
        observed_inventory = belief.lower_units
    return PolicyContext(
        forecast_target=forecast_target,
        forecast_median=forecast_median,
        observed_inventory=observed_inventory,
        pipeline_inventory=pipeline_inventory,
        lead_time_days=lead_time_days,
        shelf_life_days=shelf_life_days,
    )


def belief_audit_record(belief: InventoryBelief, source_event_ids: list[str]) -> dict[str, object]:
    """Return an audit record linking an inventory belief to source events."""
    return {**asdict(belief), "source_event_ids": "|".join(sorted(source_event_ids))}
