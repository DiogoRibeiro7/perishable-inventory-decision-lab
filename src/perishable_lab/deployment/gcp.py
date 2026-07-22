"""Dependency-free helpers for GCP batch deployment patterns."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_RESOURCE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


@dataclass(frozen=True)
class CloudRunJobSpec:
    """Minimal Cloud Run Job execution settings used by release tooling."""

    job_name: str
    region: str
    image: str
    tasks: int = 1
    max_retries: int = 2
    timeout_seconds: int = 3600
    service_account: str | None = None

    def __post_init__(self) -> None:
        if not _RESOURCE_NAME.match(self.job_name):
            raise ValueError("Cloud Run job name must be a valid lowercase resource name")
        if self.tasks < 1:
            raise ValueError("Cloud Run task count must be positive")
        if self.max_retries < 0:
            raise ValueError("Cloud Run retries cannot be negative")
        if self.timeout_seconds < 1:
            raise ValueError("Cloud Run timeout must be positive")


def deterministic_execution_id(
    *,
    workload: str,
    business_date: str,
    config_hash: str,
) -> str:
    """Return a stable idempotency key for one workload and business date."""
    if not _RESOURCE_NAME.match(workload):
        raise ValueError("Workload must be a valid lowercase resource name")
    digest = hashlib.sha256(f"{workload}|{business_date}|{config_hash}".encode()).hexdigest()
    return f"{workload}-{business_date.replace('-', '')}-{digest[:12]}"


def cloud_run_overrides(
    *,
    args: list[str],
    execution_id: str,
    environment: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a Cloud Run Job overrides payload with reproducibility metadata."""
    env = [{"name": "EXECUTION_ID", "value": execution_id}]
    for name, value in sorted((environment or {}).items()):
        env.append({"name": name, "value": value})
    return {
        "container_overrides": [
            {
                "args": args,
                "env": env,
            }
        ]
    }


def bigquery_partition_publish_sql(
    *,
    target_table: str,
    partition_field: str,
    partition_date: str,
    select_sql: str,
) -> str:
    """Build retry-safe delete-and-insert SQL for one BigQuery date partition."""
    if "`" in target_table or "`" in partition_field:
        raise ValueError("BigQuery identifiers must not contain backticks")
    return f"""
begin transaction;

delete from `{target_table}`
where {partition_field} = date('{partition_date}');

insert into `{target_table}`
{select_sql};

commit transaction;
""".strip()


__all__ = [
    "CloudRunJobSpec",
    "bigquery_partition_publish_sql",
    "cloud_run_overrides",
    "deterministic_execution_id",
]
