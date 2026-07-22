"""Batch recommendation schemas, validation, and atomic publication."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from perishable_lab.feature_store import deterministic_frame_hash

BatchStep = Literal[
    "train",
    "calibrate",
    "score",
    "simulate",
    "recommend",
    "validate",
    "stage",
    "publish",
    "rollback",
]
IssueSeverity = Literal["blocking", "warning"]


class PublicationError(RuntimeError):
    """Raised when publication cannot proceed."""


class PublicationConflictError(PublicationError):
    """Raised when a write would overwrite a newer active batch."""


class CorruptedArtifactError(PublicationError):
    """Raised when a stored batch no longer matches its manifest."""


@dataclass(frozen=True)
class BatchRequest:
    """Versioned request schema for daily recommendation jobs."""

    retailer_id: str
    business_date: str
    config_hash: str
    data_version: str
    model_version: str
    policy_version: str
    schema_version: str = "recommendation_request.v1"

    def job_id(self) -> str:
        """Return the deterministic job identifier for this request."""
        return deterministic_batch_job_id(
            retailer_id=self.retailer_id,
            business_date=self.business_date,
            config_hash=self.config_hash,
            data_version=self.data_version,
            model_version=self.model_version,
            policy_version=self.policy_version,
        )


@dataclass(frozen=True)
class ValidationConfig:
    """Operational validation thresholds before publication."""

    expected_rows: int
    expected_unit: str
    now: str
    max_input_age_hours: float = 24.0
    max_relative_jump: float = 1.5
    max_zero_to_quantity_jump: float = 24.0

    def __post_init__(self) -> None:
        if self.expected_rows < 1:
            raise ValueError("expected_rows must be positive")
        if self.max_input_age_hours < 0:
            raise ValueError("max_input_age_hours cannot be negative")


@dataclass(frozen=True)
class ValidationIssue:
    """One recommendation validation finding."""

    code: str
    severity: IssueSeverity
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Batch validation report."""

    status: Literal["pass", "fail"]
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class BatchManifest:
    """Immutable batch artifact manifest."""

    batch_id: str
    request: BatchRequest
    schema_version: str
    row_count: int
    artifact_hash: str
    state: Literal["staged"]


@dataclass(frozen=True)
class ActivePointer:
    """Atomic pointer to the active recommendation batch."""

    active_batch_id: str
    previous_batch_id: str | None
    generation: int


@dataclass(frozen=True)
class OverrideRecord:
    """Human override captured after recommendation publication."""

    store_id: str
    product_id: str
    business_date: str
    override_quantity: float
    reason: str
    user_id: str


@dataclass(frozen=True)
class WarehousePublicationPlan:
    """BigQuery and Cloud Storage target contract for batch publication."""

    staging_table: str
    active_table: str
    archive_table: str
    artifact_uri: str
    expected_generation: int


class RecommendationPublisher(Protocol):
    """Publication protocol shared by local and warehouse implementations."""

    def stage_batch(self, frame: pd.DataFrame, request: BatchRequest, validation: ValidationReport) -> BatchManifest:
        """Stage an immutable batch artifact."""

    def publish_batch(self, batch_id: str, *, expected_generation: int | None = None) -> ActivePointer:
        """Atomically publish a staged batch."""

    def rollback(self) -> ActivePointer:
        """Revert active recommendations to the previous valid batch."""

    def read_active(self) -> pd.DataFrame:
        """Read active recommendations after artifact validation."""


REQUIRED_RECOMMENDATION_COLUMNS = (
    "business_date",
    "store_id",
    "product_id",
    "recommended_order_quantity",
    "unit",
    "model_version",
    "policy_version",
    "generated_at",
    "input_feature_set_hash",
)


def batch_job_commands() -> tuple[BatchStep, ...]:
    """Return the supported batch-first job boundary."""
    return (
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


def deterministic_batch_job_id(
    *,
    retailer_id: str,
    business_date: str,
    config_hash: str,
    data_version: str,
    model_version: str,
    policy_version: str,
) -> str:
    """Build a stable job id from all inputs that affect output."""
    payload = "|".join([retailer_id, business_date, config_hash, data_version, model_version, policy_version])
    digest = deterministic_frame_hash(pd.DataFrame({"payload": [payload]}))[:12]
    return f"{_slug(retailer_id)}-{business_date.replace('-', '')}-{digest}"


def validate_recommendation_batch(
    frame: pd.DataFrame,
    request: BatchRequest,
    config: ValidationConfig,
    *,
    prior_active: pd.DataFrame | None = None,
) -> ValidationReport:
    """Validate a recommendation batch before it can be staged."""
    issues: list[ValidationIssue] = []
    missing_columns = sorted(set(REQUIRED_RECOMMENDATION_COLUMNS).difference(frame.columns))
    if missing_columns:
        issues.append(ValidationIssue("missing_columns", "blocking", f"Missing columns: {missing_columns}"))
        return ValidationReport("fail", tuple(issues))

    keys = ["business_date", "store_id", "product_id"]
    duplicate_count = int(frame.duplicated(keys).sum())
    if duplicate_count:
        issues.append(ValidationIssue("duplicate_recommendations", "blocking", f"Duplicate rows: {duplicate_count}"))
    if int(frame.shape[0]) != config.expected_rows:
        issues.append(
            ValidationIssue(
                "missing_rows",
                "blocking",
                f"Expected {config.expected_rows} rows and received {frame.shape[0]}",
            )
        )
    if bool((frame["business_date"].astype(str) != request.business_date).any()):
        issues.append(ValidationIssue("business_date_mismatch", "blocking", "Rows do not match request date"))
    if bool((frame["unit"].astype(str) != config.expected_unit).any()):
        issues.append(ValidationIssue("incompatible_units", "blocking", "Rows contain unexpected units"))
    if bool((frame["model_version"].astype(str) != request.model_version).any()):
        issues.append(ValidationIssue("stale_model", "blocking", "Rows do not match request model version"))
    if bool((frame["policy_version"].astype(str) != request.policy_version).any()):
        issues.append(ValidationIssue("incompatible_policy", "blocking", "Rows do not match request policy version"))

    quantities = pd.to_numeric(frame["recommended_order_quantity"], errors="coerce")
    if bool(quantities.isna().any()) or bool((quantities < 0).any()):
        issues.append(ValidationIssue("constraint_violation", "blocking", "Quantities must be non-negative numbers"))
    if bool((quantities % 1 != 0).any()):
        issues.append(ValidationIssue("constraint_violation", "blocking", "Quantities must be whole units"))

    generated_at = pd.to_datetime(frame["generated_at"], utc=True, errors="coerce")
    now = pd.Timestamp(config.now).tz_convert("UTC") if pd.Timestamp(config.now).tzinfo else pd.Timestamp(config.now, tz="UTC")
    age_hours = (now - generated_at).dt.total_seconds() / 3600.0
    if bool(generated_at.isna().any()) or bool((age_hours > config.max_input_age_hours).any()):
        issues.append(ValidationIssue("stale_inputs", "blocking", "Generated timestamps exceed freshness limit"))

    if prior_active is not None and not prior_active.empty:
        issues.extend(_jump_issues(frame, prior_active, config))

    status: Literal["pass", "fail"] = "fail" if any(issue.severity == "blocking" for issue in issues) else "pass"
    return ValidationReport(status, tuple(issues))


class LocalRecommendationStore:
    """Filesystem implementation with atomic active-pointer updates."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.batch_root = root / "batches"
        self.active_path = root / "active.json"
        self.batch_root.mkdir(parents=True, exist_ok=True)

    def stage_batch(self, frame: pd.DataFrame, request: BatchRequest, validation: ValidationReport) -> BatchManifest:
        """Stage recommendations idempotently after validation passes."""
        if validation.status != "pass":
            raise PublicationError("Cannot stage a batch with blocking validation issues")
        batch_id = request.job_id()
        batch_dir = self.batch_root / batch_id
        artifact_path = batch_dir / "recommendations.csv"
        manifest_path = batch_dir / "manifest.json"
        artifact_hash = deterministic_frame_hash(frame)
        if manifest_path.exists():
            manifest = self._read_manifest(batch_id)
            if manifest.artifact_hash != artifact_hash:
                raise PublicationConflictError("Existing batch id has different artifact contents")
            return manifest
        batch_dir.mkdir(parents=True, exist_ok=True)
        frame.sort_values(["business_date", "store_id", "product_id"]).to_csv(artifact_path, index=False)
        manifest = BatchManifest(
            batch_id=batch_id,
            request=request,
            schema_version="recommendation_output.v1",
            row_count=int(frame.shape[0]),
            artifact_hash=artifact_hash,
            state="staged",
        )
        _write_json_atomic(manifest_path, _manifest_to_dict(manifest))
        return manifest

    def publish_batch(self, batch_id: str, *, expected_generation: int | None = None) -> ActivePointer:
        """Publish a staged batch by atomically swapping the active pointer."""
        self._assert_artifact_valid(batch_id)
        current = self._read_active_pointer(required=False)
        current_generation = current.generation if current is not None else 0
        if expected_generation is not None and expected_generation != current_generation:
            raise PublicationConflictError("Active pointer generation changed")
        pointer = ActivePointer(
            active_batch_id=batch_id,
            previous_batch_id=current.active_batch_id if current is not None else None,
            generation=current_generation + 1,
        )
        _write_json_atomic(self.active_path, asdict(pointer))
        return pointer

    def rollback(self) -> ActivePointer:
        """Roll back to the previous active batch."""
        current = self._read_active_pointer(required=True)
        assert current is not None
        if current.previous_batch_id is None:
            raise PublicationError("No previous batch is available for rollback")
        self._assert_artifact_valid(current.previous_batch_id)
        pointer = ActivePointer(
            active_batch_id=current.previous_batch_id,
            previous_batch_id=current.active_batch_id,
            generation=current.generation + 1,
        )
        _write_json_atomic(self.active_path, asdict(pointer))
        return pointer

    def read_active(self) -> pd.DataFrame:
        """Read active recommendations after hash validation."""
        pointer = self._read_active_pointer(required=True)
        assert pointer is not None
        self._assert_artifact_valid(pointer.active_batch_id)
        return pd.read_csv(self._artifact_path(pointer.active_batch_id))

    def _artifact_path(self, batch_id: str) -> Path:
        return self.batch_root / batch_id / "recommendations.csv"

    def _manifest_path(self, batch_id: str) -> Path:
        return self.batch_root / batch_id / "manifest.json"

    def _read_manifest(self, batch_id: str) -> BatchManifest:
        payload = json.loads(self._manifest_path(batch_id).read_text(encoding="utf-8"))
        return BatchManifest(
            batch_id=payload["batch_id"],
            request=BatchRequest(**payload["request"]),
            schema_version=payload["schema_version"],
            row_count=int(payload["row_count"]),
            artifact_hash=payload["artifact_hash"],
            state="staged",
        )

    def _read_active_pointer(self, *, required: bool) -> ActivePointer | None:
        if not self.active_path.exists():
            if required:
                raise PublicationError("No active batch is published")
            return None
        payload = json.loads(self.active_path.read_text(encoding="utf-8"))
        return ActivePointer(
            active_batch_id=payload["active_batch_id"],
            previous_batch_id=payload["previous_batch_id"],
            generation=int(payload["generation"]),
        )

    def _assert_artifact_valid(self, batch_id: str) -> None:
        manifest = self._read_manifest(batch_id)
        artifact_path = self._artifact_path(batch_id)
        if not artifact_path.exists():
            raise CorruptedArtifactError("Recommendation artifact is missing")
        frame = pd.read_csv(artifact_path)
        if int(frame.shape[0]) != manifest.row_count or deterministic_frame_hash(frame) != manifest.artifact_hash:
            raise CorruptedArtifactError("Recommendation artifact does not match manifest")


def apply_human_overrides(frame: pd.DataFrame, overrides: tuple[OverrideRecord, ...]) -> pd.DataFrame:
    """Apply store-reviewed overrides while retaining the original recommendation."""
    output = frame.copy(deep=True)
    output["active_order_quantity"] = output["recommended_order_quantity"]
    output["override_reason"] = ""
    output["override_user_id"] = ""
    for override in overrides:
        mask = (
            (output["business_date"].astype(str) == override.business_date)
            & (output["store_id"].astype(str) == override.store_id)
            & (output["product_id"].astype(str) == override.product_id)
        )
        output.loc[mask, "active_order_quantity"] = override.override_quantity
        output.loc[mask, "override_reason"] = override.reason
        output.loc[mask, "override_user_id"] = override.user_id
    return output


def store_file_contract(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the read-only store-facing file contract."""
    columns = [
        "business_date",
        "store_id",
        "product_id",
        "active_order_quantity",
        "unit",
        "policy_version",
        "input_feature_set_hash",
        "override_reason",
    ]
    _raise_columns(frame, columns)
    return frame[columns].sort_values(["business_date", "store_id", "product_id"]).reset_index(drop=True)


def warehouse_publish_sql(plan: WarehousePublicationPlan, *, batch_id: str) -> str:
    """Return BigQuery SQL for delete-insert publication inside a transaction."""
    return "\n".join(
        [
            "begin transaction;",
            f"delete from `{plan.active_table}` where batch_id = '{batch_id}';",
            f"insert into `{plan.archive_table}` select * from `{plan.active_table}`;",
            f"insert into `{plan.active_table}` select * from `{plan.staging_table}` where batch_id = '{batch_id}';",
            "commit transaction;",
        ]
    )


def assert_generation_match(*, expected_generation: int, observed_generation: int) -> None:
    """Reject warehouse publication when the active pointer changed."""
    if expected_generation != observed_generation:
        raise PublicationConflictError("Observed generation does not match expected generation")


def fallback_to_previous_valid(store: RecommendationPublisher) -> ActivePointer:
    """Use the previous valid batch after a failed publish or validation."""
    return store.rollback()


def _jump_issues(frame: pd.DataFrame, prior_active: pd.DataFrame, config: ValidationConfig) -> list[ValidationIssue]:
    prior = prior_active.rename(columns={"recommended_order_quantity": "prior_quantity"})
    current = frame.merge(
        prior[["business_date", "store_id", "product_id", "prior_quantity"]],
        on=["business_date", "store_id", "product_id"],
        how="left",
    )
    new_quantity = pd.to_numeric(current["recommended_order_quantity"], errors="coerce")
    prior_quantity = pd.to_numeric(current["prior_quantity"], errors="coerce")
    relative_jump = (new_quantity - prior_quantity).abs() / prior_quantity.replace(0, pd.NA)
    zero_jump = prior_quantity.fillna(0).eq(0) & (new_quantity > config.max_zero_to_quantity_jump)
    if bool((relative_jump > config.max_relative_jump).fillna(False).any()) or bool(zero_jump.any()):
        return [ValidationIssue("implausible_jump", "blocking", "Recommended quantity changed beyond limit")]
    return []


def _manifest_to_dict(manifest: BatchManifest) -> dict[str, object]:
    payload = asdict(manifest)
    payload["request"] = asdict(manifest.request)
    return payload


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp_path, path)


def _raise_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
