from __future__ import annotations

import pandas as pd

from perishable_lab.evaluation.reporting import paired_block_bootstrap_difference
from perishable_lab.monitoring.quality import build_monitoring_report


def _health_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01"],
            "store_id": ["S001", "S001"],
            "product_id": ["P001", "P001"],
            "demand": [1.0, 2.0],
            "price": [3.0, 3.0],
            "shelf_life_days": [3.0, 3.0],
            "lead_time_days": [1.0, 1.0],
            "shrinkage_rate": [0.01, 0.01],
        }
    )


def test_monitoring_report_triggers_duplicate_and_undercoverage_alerts() -> None:
    report = build_monitoring_report(
        _health_frame(),
        {
            "empirical_coverage": 0.5,
            "mean_interval_width": 1.0,
            "approximate_crps": 0.8,
        },
        minimum_coverage=0.8,
        maximum_missing_rate=0.01,
    )

    assert report["status"] == "blocking"
    assert "duplicate_keys_detected" in report["alerts"]
    assert "forecast_undercoverage" in report["alerts"]


def test_monitoring_report_triggers_missing_rate_alert() -> None:
    frame = _health_frame().drop_duplicates(["date", "store_id", "product_id"]).copy()
    frame.loc[0, "price"] = None

    report = build_monitoring_report(
        frame,
        {
            "empirical_coverage": 1.0,
            "mean_interval_width": 1.0,
            "approximate_crps": 0.8,
        },
        minimum_coverage=0.8,
        maximum_missing_rate=0.01,
    )

    assert report["status"] == "blocking"
    assert "missing_rate_exceeded" in report["alerts"]


def test_paired_block_bootstrap_difference_is_reproducible() -> None:
    frame = pd.DataFrame(
        {
            "baseline": [5.0, 6.0, 7.0, 8.0],
            "candidate": [4.0, 5.0, 7.0, 7.0],
        }
    )

    first = paired_block_bootstrap_difference(
        frame,
        baseline_column="baseline",
        candidate_column="candidate",
        n_resamples=50,
        seed=3,
    )
    second = paired_block_bootstrap_difference(
        frame,
        baseline_column="baseline",
        candidate_column="candidate",
        n_resamples=50,
        seed=3,
    )

    assert first == second
    assert first["mean_difference"] < 0.0
