from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.feature_store import (
    DuplicateFeatureVersionError,
    FeatureMetadata,
    FeatureRegistry,
    deterministic_frame_hash,
    feature_set_hash,
    freeze_training_snapshot,
    order_cutoff_timestamps,
    parity_report,
    point_in_time_join,
    source_partition_manifest,
    validate_null_policies,
)


def _registry() -> FeatureRegistry:
    return FeatureRegistry(
        (
            FeatureMetadata(
                name="stock_on_hand",
                owner="data-platform",
                source="inventory_snapshots",
                transformation="latest_available_count",
                unit="unit",
                availability_delay_hours=2.0,
                freshness_sla_hours=6.0,
                null_policy="fail",
                version="v1",
            ),
        )
    )


def test_point_in_time_join_includes_cutoff_equal_rows() -> None:
    spine = pd.DataFrame(
        {
            "store_id": ["s1"],
            "product_id": ["p1"],
            "cutoff_at": ["2026-01-05T06:00:00Z"],
        }
    )
    features = pd.DataFrame(
        {
            "store_id": ["s1"],
            "product_id": ["p1"],
            "effective_at": ["2026-01-05T05:00:00Z"],
            "available_at": ["2026-01-05T06:00:00Z"],
            "feature_version": ["v1"],
            "source_record_id": ["count-1"],
            "stock_on_hand": [12.0],
        }
    )

    joined = point_in_time_join(
        spine,
        features,
        entity_columns=("store_id", "product_id"),
        cutoff_column="cutoff_at",
        feature_columns=("stock_on_hand",),
        source_record_column="source_record_id",
    )

    assert joined.loc[0, "stock_on_hand"] == 12.0
    assert joined.loc[0, "feature_source_record_id"] == "count-1"


def test_point_in_time_join_excludes_late_rows_and_keeps_prior_version() -> None:
    spine = pd.DataFrame(
        {
            "store_id": ["s1"],
            "product_id": ["p1"],
            "cutoff_at": ["2026-01-05T06:00:00Z"],
        }
    )
    features = pd.DataFrame(
        {
            "store_id": ["s1", "s1"],
            "product_id": ["p1", "p1"],
            "effective_at": ["2026-01-04T00:00:00Z", "2026-01-04T00:00:00Z"],
            "available_at": ["2026-01-05T05:59:00Z", "2026-01-05T06:01:00Z"],
            "feature_version": ["v1", "v2"],
            "stock_on_hand": [8.0, 3.0],
        }
    )

    joined = point_in_time_join(
        spine,
        features,
        entity_columns=("store_id", "product_id"),
        cutoff_column="cutoff_at",
        feature_columns=("stock_on_hand",),
    )

    assert joined.loc[0, "stock_on_hand"] == 8.0
    assert joined.loc[0, "feature_version"] == "v1"


def test_duplicate_versions_are_rejected() -> None:
    spine = pd.DataFrame({"store_id": ["s1"], "product_id": ["p1"], "cutoff_at": ["2026-01-05T06:00:00Z"]})
    features = pd.DataFrame(
        {
            "store_id": ["s1", "s1"],
            "product_id": ["p1", "p1"],
            "effective_at": ["2026-01-04T00:00:00Z", "2026-01-04T00:00:00Z"],
            "available_at": ["2026-01-05T05:00:00Z", "2026-01-05T05:00:00Z"],
            "feature_version": ["v1", "v1"],
            "stock_on_hand": [8.0, 9.0],
        }
    )

    with pytest.raises(DuplicateFeatureVersionError):
        point_in_time_join(
            spine,
            features,
            entity_columns=("store_id", "product_id"),
            cutoff_column="cutoff_at",
            feature_columns=("stock_on_hand",),
        )


def test_null_policy_reports_blocking_features() -> None:
    frame = pd.DataFrame({"stock_on_hand": [1.0, None]})

    issues = validate_null_policies(frame, _registry())

    assert issues[0].feature_name == "stock_on_hand"
    assert issues[0].null_count == 1


def test_cutoffs_handle_daylight_saving_boundary() -> None:
    cutoffs = order_cutoff_timestamps(
        pd.Series(["2026-03-28", "2026-03-29"]),
        timezone="Europe/Lisbon",
        cutoff_hour=6,
    )

    assert str(cutoffs.iloc[0]) == "2026-03-28 06:00:00+00:00"
    assert str(cutoffs.iloc[1]) == "2026-03-29 05:00:00+00:00"


def test_parity_report_uses_numeric_tolerance() -> None:
    local = pd.DataFrame({"store_id": ["s1"], "product_id": ["p1"], "stock_on_hand": [1.0000001]})
    warehouse = pd.DataFrame({"store_id": ["s1"], "product_id": ["p1"], "stock_on_hand": [1.0000002]})

    report = parity_report(
        local,
        warehouse,
        key_columns=("store_id", "product_id"),
        feature_columns=("stock_on_hand",),
        tolerance=1e-6,
    )

    assert report.status == "pass"
    assert report.rows_compared == 1


def test_feature_hashes_and_manifests_are_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-01-06", "2026-01-05"],
            "store_id": ["s1", "s1"],
            "product_id": ["p1", "p1"],
            "stock_on_hand": [4.0, 3.0],
        }
    )
    shuffled = frame.sample(frac=1.0, random_state=5)
    manifest = source_partition_manifest({"inventory_snapshots": frame}, partition_columns=("date",))

    assert deterministic_frame_hash(frame) == deterministic_frame_hash(shuffled)
    assert feature_set_hash(frame, _registry(), manifest) == feature_set_hash(shuffled, _registry(), manifest)
    assert freeze_training_snapshot(frame, _registry(), manifest)["rows"] == 2
