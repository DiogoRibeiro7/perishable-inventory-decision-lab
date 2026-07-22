from __future__ import annotations

import pytest

from perishable_lab.deployment import (
    CloudRunJobSpec,
    bigquery_partition_publish_sql,
    cloud_run_overrides,
    deterministic_execution_id,
)


def test_deterministic_execution_id_is_stable() -> None:
    first = deterministic_execution_id(
        workload="daily-decisions",
        business_date="2026-01-05",
        config_hash="abc123",
    )
    second = deterministic_execution_id(
        workload="daily-decisions",
        business_date="2026-01-05",
        config_hash="abc123",
    )

    assert first == second
    assert first.startswith("daily-decisions-20260105-")


def test_cloud_run_overrides_include_sorted_environment() -> None:
    overrides = cloud_run_overrides(
        args=["score", "--date", "2026-01-05"],
        execution_id="daily-decisions-20260105-deadbeef0000",
        environment={"B": "2", "A": "1"},
    )

    container = overrides["container_overrides"][0]
    assert container["args"] == ["score", "--date", "2026-01-05"]
    assert container["env"] == [
        {"name": "EXECUTION_ID", "value": "daily-decisions-20260105-deadbeef0000"},
        {"name": "A", "value": "1"},
        {"name": "B", "value": "2"},
    ]


def test_bigquery_partition_publish_sql_is_delete_insert_transaction() -> None:
    sql = bigquery_partition_publish_sql(
        target_table="project.dataset.table",
        partition_field="decision_date",
        partition_date="2026-01-05",
        select_sql="select * from `project.dataset.stage`",
    )

    assert sql.startswith("begin transaction;")
    assert "delete from `project.dataset.table`" in sql
    assert "decision_date = date('2026-01-05')" in sql
    assert sql.endswith("commit transaction;")


def test_cloud_run_job_spec_rejects_invalid_settings() -> None:
    with pytest.raises(ValueError, match="resource name"):
        CloudRunJobSpec(job_name="Bad_Name", region="europe-west1", image="image")
