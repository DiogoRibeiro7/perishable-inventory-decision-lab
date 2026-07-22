from __future__ import annotations

import pandas as pd

from perishable_lab.events import (
    EventFeatureConfig,
    build_event_features,
    build_event_window_diagnostics,
    causal_caution_text,
    promotion_segment_report,
)


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "store_id": ["S001"] * 5,
            "product_id": ["P001"] * 5,
            "demand": [10, 12, 25, 24, 11],
            "baseline_velocity": [10.0] * 5,
            "shelf_life_days": [3] * 5,
        }
    )


def test_event_features_use_latest_revision_known_by_cutoff() -> None:
    events = pd.DataFrame(
        [
            {
                "date": "2026-01-03",
                "store_id": "S001",
                "product_id": "P001",
                "known_at": "2026-01-02T05:00:00Z",
                "regular_price": 10.0,
                "planned_price": 8.0,
                "planned_promotion": 1,
                "published_promotion": 1,
                "executed_promotion": 0,
                "promotion_type": "flyer",
                "promotion_status": "planned",
                "event_start": "2026-01-03",
                "event_end": "2026-01-04",
            },
            {
                "date": "2026-01-03",
                "store_id": "S001",
                "product_id": "P001",
                "known_at": "2026-01-03T12:00:00Z",
                "regular_price": 10.0,
                "planned_price": 6.0,
                "planned_promotion": 1,
                "published_promotion": 1,
                "executed_promotion": 1,
                "promotion_type": "flyer",
                "promotion_status": "executed",
                "event_start": "2026-01-03",
                "event_end": "2026-01-04",
            },
        ]
    )

    featured = build_event_features(_base_frame(), events, config=EventFeatureConfig(decision_cutoff_hour=6))
    row = featured[featured["date"] == pd.Timestamp("2026-01-03")].iloc[0]

    assert row["planned_price"] == 8.0
    assert row["executed_promotion"] == 0
    assert row["discount_depth"] == 0.2


def test_event_windows_and_missing_plans_are_explicit() -> None:
    events = pd.DataFrame(
        [
            {
                "date": "2026-01-03",
                "store_id": "S001",
                "product_id": "P001",
                "known_at": "2026-01-01T05:00:00Z",
                "regular_price": 10.0,
                "planned_price": 8.0,
                "planned_promotion": 1,
                "promotion_type": "display",
                "promotion_status": "planned",
                "event_start": "2026-01-03",
                "event_end": "2026-01-03",
            }
        ]
    )

    featured = build_event_features(_base_frame(), events, config=EventFeatureConfig(pre_event_days=2, post_event_days=1))

    assert featured.loc[0, "event_window"] == "pre_promotion"
    assert featured.loc[1, "event_window"] == "pre_promotion"
    assert featured.loc[2, "event_window"] == "active_promotion"
    assert featured.loc[3, "event_window"] == "post_promotion"
    assert featured.loc[4, "promotion_type"] == "unknown"


def test_cancelled_promotions_are_not_active_windows() -> None:
    events = pd.DataFrame(
        [
            {
                "date": "2026-01-03",
                "store_id": "S001",
                "product_id": "P001",
                "known_at": "2026-01-02T05:00:00Z",
                "regular_price": 10.0,
                "planned_price": 8.0,
                "planned_promotion": 1,
                "promotion_status": "cancelled",
            }
        ]
    )

    featured = build_event_features(_base_frame(), events)

    assert featured.loc[2, "cancelled_promotion"]
    assert featured.loc[2, "event_window"] == "normal"


def test_calendar_join_is_as_of_safe() -> None:
    calendar = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "store_id": "S001",
                "known_at": "2026-01-01T05:00:00Z",
                "public_holiday": False,
            },
            {
                "date": "2026-01-02",
                "store_id": "S001",
                "known_at": "2026-01-02T12:00:00Z",
                "public_holiday": True,
            },
        ]
    )

    featured = build_event_features(_base_frame(), pd.DataFrame(), calendar=calendar)

    assert not bool(featured.loc[1, "public_holiday"])


def test_event_diagnostics_and_segment_report_are_deterministic() -> None:
    frame = _base_frame()
    frame["event_window"] = ["normal", "normal", "active_promotion", "active_promotion", "post_promotion"]
    frame["q05"] = [5, 6, 15, 16, 6]
    frame["q50"] = [9, 10, 20, 21, 9]
    frame["q95"] = [15, 16, 30, 30, 15]

    diagnostics = build_event_window_diagnostics(frame)
    report = promotion_segment_report(frame)

    assert set(diagnostics["event_window"]) == {"active_promotion", "normal", "post_promotion"}
    assert set(report["event_window"]) == {"active_promotion", "normal", "post_promotion"}
    assert "predictive uplift is not causal" in causal_caution_text()
