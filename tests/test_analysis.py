from __future__ import annotations

from pathlib import Path

import pandas as pd

from perishable_lab.analysis import ProfileConfig, profile_daily_frame, write_profile_report
from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand


def _profile_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-02",
                "2026-01-04",
                "2026-01-01",
            ],
            "store_id": ["S001", "S001", "S001", "S001", "S002"],
            "product_id": ["P001", "P001", "P001", "P001", "P002"],
            "demand": [0, 5, 5, 500, 2],
            "observed_inventory": [0, 10, 10, 200, -1],
            "promotion": [1, 0, 0, 0, 0],
            "discount_depth": [0.0, 0.0, 0.0, 0.0, 0.0],
            "shelf_life_days": [3, 3, 3, 3, 2],
            "lead_time_days": [1, 1, 1, 1, 1],
        }
    )


def test_profile_detects_missing_days_and_duplicate_keys() -> None:
    result = profile_daily_frame(_profile_frame(), config=ProfileConfig(min_segment_size=2))
    rule_ids = {issue.rule_id for issue in result.quality_issues}

    assert "duplicate_business_key" in rule_ids
    assert "missing_store_product_days" in rule_ids


def test_profile_uses_robust_outlier_summaries() -> None:
    result = profile_daily_frame(_profile_frame(), config=ProfileConfig(min_segment_size=2))
    outlier_count = result.global_summary.loc[
        result.global_summary["metric"] == "outlier_count", "value"
    ].iloc[0]

    assert int(outlier_count) == 1


def test_profile_detects_impossible_stock_transitions_and_censoring() -> None:
    result = profile_daily_frame(_profile_frame(), config=ProfileConfig(min_segment_size=2))
    rule_ids = {issue.rule_id for issue in result.quality_issues}

    assert "negative_observed_inventory" in rule_ids
    assert "impossible_observed_inventory_jump" in rule_ids
    assert "stockout_censoring_evidence" in rule_ids


def test_profile_suppresses_tiny_segments() -> None:
    result = profile_daily_frame(_profile_frame(), config=ProfileConfig(min_segment_size=4))
    suppressed = result.segment_summary[
        (result.segment_summary["segment_type"] == "store_id")
        & (result.segment_summary["segment_value"] == "S002")
    ].iloc[0]

    assert bool(suppressed["suppressed"])
    assert pd.isna(suppressed["median_demand"])


def test_profile_report_output_is_deterministic(tmp_path: Path) -> None:
    frame = _profile_frame()
    first = tmp_path / "first"
    second = tmp_path / "second"

    write_profile_report(frame, first, config=ProfileConfig(min_segment_size=2))
    write_profile_report(frame, second, config=ProfileConfig(min_segment_size=2))

    for name in (
        "global_summary.csv",
        "segment_summary.csv",
        "quality_issues.csv",
        "data_quality_rules.csv",
        "chart_metadata.csv",
        "profile_report.md",
    ):
        assert (first / name).read_text(encoding="utf-8") == (second / name).read_text(
            encoding="utf-8"
        )


def test_profile_preserves_source_values() -> None:
    frame = _profile_frame()
    before = frame.copy(deep=True)

    profile_daily_frame(frame, config=ProfileConfig(min_segment_size=2))

    pd.testing.assert_frame_equal(frame, before)


def test_profile_writes_empty_issue_table_for_clean_data(tmp_path: Path) -> None:
    frame = generate_daily_demand(SyntheticDataSpec(days=60, stores=1, products=1, seed=7))

    result = write_profile_report(frame, tmp_path, config=ProfileConfig(min_segment_size=2))

    assert result.quality_issues_frame().empty
    assert "rule_id" in pd.read_csv(tmp_path / "quality_issues.csv").columns
