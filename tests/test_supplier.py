from __future__ import annotations

import pandas as pd

from perishable_lab.supplier import (
    ContractualLeadTimeModel,
    EmpiricalLeadTimeModel,
    add_valid_delivery_days,
    detect_supplier_shock,
    prepare_delivery_events,
    protect_random_lead_time_demand,
    simulation_controls_from_scenario,
    supplier_distribution_manifest,
)


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4"],
            "supplier_id": ["SUP1", "SUP1", "SUP1", "SUP1"],
            "product_id": ["P001", "P001", "P001", "P001"],
            "created_at": [
                "2026-01-01T08:00:00Z",
                "2026-01-02T08:00:00Z",
                "2026-01-03T08:00:00Z",
                "2026-01-04T08:00:00Z",
            ],
            "requested_delivery_date": [
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
            ],
            "arrival_at": [
                "2026-01-02T08:00:00Z",
                "2026-01-04T08:00:00Z",
                "2026-01-05T08:00:00Z",
                "2026-01-05T08:00:00Z",
            ],
            "ordered_quantity": [10, 10, 10, 10],
            "accepted_quantity": [10, 5, 0, 10],
            "rejected_quantity": [0, 0, 10, 0],
            "cancelled": [False, False, False, False],
        }
    )


def test_delivery_calendar_skips_weekend_crossings() -> None:
    calendar = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-02", periods=5, freq="D"),
            "can_deliver": [True, False, False, True, True],
        }
    )

    assert add_valid_delivery_days("2026-01-02", 1, calendar) == pd.Timestamp("2026-01-05")


def test_prepare_delivery_events_marks_partial_and_rejected_deliveries() -> None:
    prepared = prepare_delivery_events(_events())

    assert prepared["partial_fulfilment"].tolist() == [False, True, True, False]
    assert prepared["rejected_delivery"].tolist() == [False, False, True, False]
    assert prepared["late_delivery"].tolist() == [False, True, True, False]


def test_empirical_model_samples_replayable_scenarios_and_adapter() -> None:
    model = EmpiricalLeadTimeModel.fit(
        _events(),
        fallback=ContractualLeadTimeModel(lead_time_days=1),
        min_samples=3,
        version="empirical:test",
    )
    distribution = model.distribution_for("SUP1", "P001")

    first = distribution.sample(4, seed=9)
    second = distribution.sample(4, seed=9)
    controls = simulation_controls_from_scenario(first.iloc[0])

    pd.testing.assert_frame_equal(first, second)
    assert distribution.expected_fill_rate == 0.625
    assert controls.supplier_fill_rate == first.loc[0, "supplier_fill_rate"]


def test_new_supplier_lane_uses_contractual_fallback() -> None:
    model = EmpiricalLeadTimeModel.fit(
        _events(),
        fallback=ContractualLeadTimeModel(lead_time_days=2),
        min_samples=3,
    )

    distribution = model.distribution_for("SUP9", "P999")

    assert distribution.source == "fallback_contractual"
    assert distribution.support_lead_time_days == (2,)


def test_random_lead_time_protection_uses_scenario_horizons() -> None:
    scenarios = pd.DataFrame({"lead_time_days": [1, 2, 3]})
    daily_forecast = pd.Series([5.0, 6.0, 7.0])

    assert protect_random_lead_time_demand(daily_forecast, scenarios, quantile=1.0) == 18.0


def test_supplier_shock_triggers_fallback() -> None:
    shock = detect_supplier_shock(_events(), window=3, minimum_fill_rate=0.8, maximum_late_rate=0.5)

    assert bool(shock.loc[0, "fallback_required"])
    assert shock.loc[0, "reason"] == "supplier_shock"


def test_distribution_manifest_states_reliability_version() -> None:
    distribution = ContractualLeadTimeModel(lead_time_days=1).distribution_for("SUP1", "P001")

    manifest = supplier_distribution_manifest(distribution)

    assert manifest["version"] == "contractual:v1"
