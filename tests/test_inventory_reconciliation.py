from __future__ import annotations

import numpy as np
import pandas as pd

from perishable_lab.inventory import (
    ParticleInventoryEstimator,
    belief_audit_record,
    build_reconciliation_report,
    conservative_interval_belief,
    policy_context_from_belief,
    replay_stock_ledger,
)


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e3", "e4", "e5"],
            "event_type": ["delivery", "sale", "waste", "return", "count"],
            "event_time": [
                "2026-01-01T08:00:00Z",
                "2026-01-01T12:00:00Z",
                "2026-01-01T15:00:00Z",
                "2026-01-02T09:00:00Z",
                "2026-01-02T18:00:00Z",
            ],
            "processing_time": [
                "2026-01-01T08:01:00Z",
                "2026-01-01T12:01:00Z",
                "2026-01-01T15:01:00Z",
                "2026-01-02T09:01:00Z",
                "2026-01-02T18:01:00Z",
            ],
            "revision": [0, 0, 0, 0, 0],
            "store_id": ["S001"] * 5,
            "product_id": ["P001"] * 5,
            "quantity": [20, 6, 2, 1, 10],
        }
    )


def test_stock_ledger_mass_balance() -> None:
    ledger = replay_stock_ledger(_events())

    assert ledger["closing_reconstructed_stock"].tolist() == [20, 14, 12, 13, 10]
    assert ledger.iloc[-1]["closing_reconstructed_stock"] == 10


def test_late_revisions_are_replayed_deterministically_and_reported() -> None:
    events = _events()
    revised = events.iloc[[1]].copy()
    revised["quantity"] = 7
    revised["revision"] = 1
    revised["processing_time"] = "2026-01-04T12:00:00Z"
    events = pd.concat([events, revised], ignore_index=True)

    ledger = replay_stock_ledger(events)
    report = build_reconciliation_report(events, ledger)

    assert ledger.loc[ledger["event_id"] == "e2", "quantity"].iloc[0] == 7
    assert "late_inventory_revision" in set(report["rule_id"])
    assert "duplicate_event_revision" in set(report["rule_id"])


def test_contradictory_counts_are_flagged() -> None:
    events = _events()
    events.loc[4, "quantity"] = 100
    ledger = replay_stock_ledger(events)

    report = build_reconciliation_report(events, ledger, count_discrepancy_threshold=5)

    assert "contradictory_count" in set(report["rule_id"])


def test_particle_replay_is_deterministic() -> None:
    estimator = ParticleInventoryEstimator(seed=11, particles=50)
    particles = estimator.initial_particles(20.0)
    first = estimator.predict(particles, delta=-5.0)
    second = estimator.predict(particles, delta=-5.0)

    np.testing.assert_allclose(first, second)


def test_uncertainty_grows_without_observations_and_reduces_after_count() -> None:
    estimator = ParticleInventoryEstimator(seed=11, particles=500, process_noise_std=2.0)
    initial = estimator.initial_particles(20.0)
    predicted = estimator.predict(initial, delta=-3.0)
    updated = estimator.update_with_count(predicted, counted_units=16.0, trust=0.9)

    assert predicted.std() > initial.std()
    assert updated.std() < predicted.std()


def test_policy_adapter_uses_lower_bound_when_uncertainty_is_high() -> None:
    belief = conservative_interval_belief(
        store_id="S001",
        product_id="P001",
        recorded_units=12.0,
        uncertainty_units=8.0,
    )

    context = policy_context_from_belief(
        belief,
        forecast_target=20.0,
        forecast_median=12.0,
        pipeline_inventory=3.0,
        uncertainty_threshold=5.0,
    )

    assert context.observed_inventory == 4.0
    assert belief_audit_record(belief, ["e2", "e1"])["source_event_ids"] == "e1|e2"
