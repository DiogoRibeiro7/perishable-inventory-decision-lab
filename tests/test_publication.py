from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.publication import (
    BatchRequest,
    CorruptedArtifactError,
    LocalRecommendationStore,
    OverrideRecord,
    PublicationConflictError,
    PublicationError,
    ValidationConfig,
    WarehousePublicationPlan,
    apply_human_overrides,
    assert_generation_match,
    batch_job_commands,
    fallback_to_previous_valid,
    store_file_contract,
    validate_recommendation_batch,
    warehouse_publish_sql,
)


def _request(model_version: str = "model-v1", policy_version: str = "policy-v1") -> BatchRequest:
    return BatchRequest(
        retailer_id="fresh-market",
        business_date="2026-01-05",
        config_hash="cfg123",
        data_version="data456",
        model_version=model_version,
        policy_version=policy_version,
    )


def _batch(quantity: int = 6, model_version: str = "model-v1", policy_version: str = "policy-v1") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "business_date": ["2026-01-05"],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "recommended_order_quantity": [quantity],
            "unit": ["unit"],
            "model_version": [model_version],
            "policy_version": [policy_version],
            "generated_at": ["2026-01-05T06:00:00Z"],
            "input_feature_set_hash": ["features123"],
        }
    )


def _validation(expected_rows: int = 1) -> ValidationConfig:
    return ValidationConfig(expected_rows=expected_rows, expected_unit="unit", now="2026-01-05T07:00:00Z")


def test_job_id_is_deterministic_and_commands_are_separate() -> None:
    assert _request().job_id() == _request().job_id()
    assert batch_job_commands() == (
        "train",
        "calibrate",
        "score",
        "simulate",
        "recommend",
        "validate",
        "stage",
        "publish",
        "rollback",
    )


def test_retries_stage_the_same_batch_idempotently(tmp_path) -> None:  # type: ignore[no-untyped-def]
    frame = _batch()
    report = validate_recommendation_batch(frame, _request(), _validation())
    store = LocalRecommendationStore(tmp_path)

    first = store.stage_batch(frame, _request(), report)
    second = store.stage_batch(frame, _request(), report)

    assert first == second
    assert store.publish_batch(first.batch_id).active_batch_id == first.batch_id


def test_failed_partition_does_not_replace_active_batch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = LocalRecommendationStore(tmp_path)
    good = _batch()
    good_report = validate_recommendation_batch(good, _request(), _validation())
    manifest = store.stage_batch(good, _request(), good_report)
    store.publish_batch(manifest.batch_id)
    incomplete = _batch(quantity=7).iloc[0:0]
    bad_report = validate_recommendation_batch(incomplete, _request(), _validation(expected_rows=1))

    with pytest.raises(PublicationError):
        store.stage_batch(incomplete, _request(), bad_report)

    assert store.read_active().loc[0, "recommended_order_quantity"] == 6


def test_validation_catches_stale_model_policy_units_and_jumps() -> None:
    frame = _batch(quantity=50, model_version="old-model", policy_version="wrong-policy")
    frame["unit"] = "case"
    prior = _batch(quantity=1)

    report = validate_recommendation_batch(frame, _request(), _validation(), prior_active=prior)
    codes = {issue.code for issue in report.issues}

    assert report.status == "fail"
    assert {"stale_model", "incompatible_policy", "incompatible_units", "implausible_jump"}.issubset(codes)


def test_generation_mismatch_blocks_warehouse_publish() -> None:
    with pytest.raises(PublicationConflictError):
        assert_generation_match(expected_generation=4, observed_generation=5)

    plan = WarehousePublicationPlan(
        staging_table="project.dataset.stage",
        active_table="project.dataset.active",
        archive_table="project.dataset.archive",
        artifact_uri="gs://bucket/recommendations/batch.csv",
        expected_generation=4,
    )

    sql = warehouse_publish_sql(plan, batch_id="batch-1")
    assert sql.startswith("begin transaction;")
    assert "project.dataset.active" in sql


def test_corrupted_artifact_is_not_served(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = LocalRecommendationStore(tmp_path)
    frame = _batch()
    report = validate_recommendation_batch(frame, _request(), _validation())
    manifest = store.stage_batch(frame, _request(), report)
    store.publish_batch(manifest.batch_id)
    artifact_path = tmp_path / "batches" / manifest.batch_id / "recommendations.csv"
    artifact_path.write_text("broken\n1\n", encoding="utf-8")

    with pytest.raises(CorruptedArtifactError):
        store.read_active()


def test_rollback_and_store_contract_use_previous_valid_batch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = LocalRecommendationStore(tmp_path)
    first = _batch(quantity=6)
    first_manifest = store.stage_batch(first, _request(), validate_recommendation_batch(first, _request(), _validation()))
    store.publish_batch(first_manifest.batch_id)
    second_request = BatchRequest(
        retailer_id="fresh-market",
        business_date="2026-01-05",
        config_hash="cfg124",
        data_version="data456",
        model_version="model-v1",
        policy_version="policy-v1",
    )
    second = _batch(quantity=8)
    second_manifest = store.stage_batch(second, second_request, validate_recommendation_batch(second, second_request, _validation()))
    store.publish_batch(second_manifest.batch_id)

    pointer = fallback_to_previous_valid(store)
    active = apply_human_overrides(
        store.read_active(),
        (
            OverrideRecord(
                store_id="s1",
                product_id="p1",
                business_date="2026-01-05",
                override_quantity=5,
                reason="manager_adjustment",
                user_id="u1",
            ),
        ),
    )
    contract = store_file_contract(active)

    assert pointer.active_batch_id == first_manifest.batch_id
    assert contract.loc[0, "active_order_quantity"] == 5
    assert contract.loc[0, "override_reason"] == "manager_adjustment"
