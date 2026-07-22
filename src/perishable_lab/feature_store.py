"""Point-in-time feature registry, joins, lineage, and parity checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NullPolicy = Literal["allow", "zero_fill", "forward_fill", "fail"]
ParityStatus = Literal["pass", "fail"]


class DuplicateFeatureVersionError(ValueError):
    """Raised when feature records have ambiguous versions."""


@dataclass(frozen=True)
class FeatureMetadata:
    """Feature registry entry with availability and ownership semantics."""

    name: str
    owner: str
    source: str
    transformation: str
    unit: str
    availability_delay_hours: float
    freshness_sla_hours: float
    null_policy: NullPolicy
    version: str
    dtype: str = "float"

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("Feature name and version are required")
        if self.availability_delay_hours < 0 or self.freshness_sla_hours < 0:
            raise ValueError("Availability and freshness values cannot be negative")


@dataclass(frozen=True)
class FeatureRegistry:
    """Immutable feature registry snapshot."""

    features: tuple[FeatureMetadata, ...]

    def __post_init__(self) -> None:
        keys = [(feature.name, feature.version) for feature in self.features]
        if len(keys) != len(set(keys)):
            raise DuplicateFeatureVersionError("Duplicate feature name and version")

    def names(self) -> tuple[str, ...]:
        """Return feature names in deterministic registry order."""
        return tuple(feature.name for feature in self.features)

    def by_name(self) -> dict[str, FeatureMetadata]:
        """Return the latest registered metadata for each feature name."""
        ordered = sorted(self.features, key=lambda item: (item.name, item.version))
        return {feature.name: feature for feature in ordered}

    def as_frame(self) -> pd.DataFrame:
        """Return a tabular registry for docs and lineage export."""
        return pd.DataFrame([asdict(feature) for feature in self.features]).sort_values(
            ["name", "version"],
            ignore_index=True,
        )


@dataclass(frozen=True)
class NullPolicyIssue:
    """A feature that violates its registered null policy."""

    feature_name: str
    null_count: int
    policy: NullPolicy


@dataclass(frozen=True)
class ParityReport:
    """Comparison between local and warehouse feature values."""

    status: ParityStatus
    rows_compared: int
    mismatched_columns: tuple[str, ...]
    max_abs_differences: dict[str, float]


def time_semantics() -> dict[str, str]:
    """Define timestamp fields used throughout feature generation."""
    return {
        "event_time": "when the source event happened",
        "effective_time": "when the source value becomes true for the business entity",
        "ingestion_time": "when the record first arrived in the platform",
        "processing_time": "when the feature transformation ran",
        "business_date": "the store operating date used for planning and reporting",
    }


def order_cutoff_timestamps(
    business_dates: pd.Series,
    *,
    timezone: str,
    cutoff_hour: int,
    cutoff_minute: int = 0,
) -> pd.Series:
    """Convert local business dates and cutoff time into UTC timestamps."""
    if not 0 <= cutoff_hour <= 23 or not 0 <= cutoff_minute <= 59:
        raise ValueError("Cutoff time is outside the daily clock")
    dates = pd.to_datetime(business_dates).dt.strftime("%Y-%m-%d")
    local_naive = pd.to_datetime(dates) + pd.to_timedelta(cutoff_hour, unit="h") + pd.to_timedelta(
        cutoff_minute, unit="m"
    )
    localized = local_naive.dt.tz_localize(
        ZoneInfo(timezone),
        ambiguous=np.full(len(local_naive), True),
        nonexistent="shift_forward",
    )
    return localized.dt.tz_convert("UTC")


def point_in_time_join(
    spine: pd.DataFrame,
    features: pd.DataFrame,
    *,
    entity_columns: tuple[str, ...],
    cutoff_column: str,
    feature_columns: tuple[str, ...],
    effective_time_column: str = "effective_at",
    available_time_column: str = "available_at",
    version_column: str = "feature_version",
    source_record_column: str | None = None,
) -> pd.DataFrame:
    """Join latest available feature values at or before each order cutoff."""
    required_spine = set(entity_columns).union({cutoff_column})
    required_features = set(entity_columns).union(
        {effective_time_column, available_time_column, version_column, *feature_columns}
    )
    if source_record_column is not None:
        required_features.add(source_record_column)
    _raise_missing("spine", spine, required_spine)
    _raise_missing("features", features, required_features)

    version_key = [*entity_columns, effective_time_column, available_time_column, version_column]
    duplicates = features.duplicated(version_key, keep=False)
    if bool(duplicates.any()):
        raise DuplicateFeatureVersionError("Duplicate feature rows for the same version key")

    left = spine.copy(deep=True).reset_index(drop=True)
    left["_prediction_row_id"] = np.arange(len(left))
    left["_cutoff_utc"] = _to_utc(left[cutoff_column])
    right = features.copy(deep=True)
    right["_effective_utc"] = _to_utc(right[effective_time_column])
    right["_available_utc"] = _to_utc(right[available_time_column])

    joined = left.merge(right, on=list(entity_columns), how="left", suffixes=("", "_feature"))
    eligible = (joined["_effective_utc"] <= joined["_cutoff_utc"]) & (
        joined["_available_utc"] <= joined["_cutoff_utc"]
    )
    joined = joined.loc[eligible].copy()
    selected_columns = [
        "_prediction_row_id",
        *feature_columns,
        effective_time_column,
        available_time_column,
        version_column,
    ]
    if source_record_column is not None:
        selected_columns.append(source_record_column)
    if joined.empty:
        return left.drop(columns=["_cutoff_utc"])
    latest = (
        joined.sort_values(["_prediction_row_id", "_effective_utc", "_available_utc", version_column])
        .drop_duplicates("_prediction_row_id", keep="last")[selected_columns]
        .reset_index(drop=True)
    )
    latest = latest.rename(
        columns={
            effective_time_column: "feature_effective_at",
            available_time_column: "feature_available_at",
            version_column: "feature_version",
            **({source_record_column: "feature_source_record_id"} if source_record_column is not None else {}),
        }
    )
    return left.drop(columns=["_cutoff_utc"]).merge(latest, on="_prediction_row_id", how="left").drop(
        columns=["_prediction_row_id"]
    )


def validate_null_policies(frame: pd.DataFrame, registry: FeatureRegistry) -> tuple[NullPolicyIssue, ...]:
    """Return features that violate a fail-on-null policy."""
    issues: list[NullPolicyIssue] = []
    for metadata in registry.features:
        if metadata.null_policy != "fail" or metadata.name not in frame.columns:
            continue
        null_count = int(frame[metadata.name].isna().sum())
        if null_count:
            issues.append(NullPolicyIssue(metadata.name, null_count, metadata.null_policy))
    return tuple(issues)


def deterministic_frame_hash(frame: pd.DataFrame, *, columns: tuple[str, ...] | None = None) -> str:
    """Hash data values deterministically, independent of row order."""
    active_columns = tuple(columns or tuple(sorted(frame.columns)))
    prepared = frame.loc[:, list(active_columns)].copy(deep=True)
    for column in active_columns:
        prepared[column] = prepared[column].map(_stable_value)
    prepared = prepared.sort_values(list(active_columns), ignore_index=True)
    payload = prepared.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode()).hexdigest()


def source_partition_manifest(
    sources: Mapping[str, pd.DataFrame],
    *,
    partition_columns: tuple[str, ...],
) -> dict[str, object]:
    """Create source partition row counts and hashes for frozen runs."""
    manifest: dict[str, object] = {}
    for source_name, frame in sorted(sources.items()):
        _raise_missing(source_name, frame, set(partition_columns))
        partitions: list[dict[str, object]] = []
        for keys, group in frame.groupby(list(partition_columns), dropna=False, sort=True):
            key_tuple = keys if isinstance(keys, tuple) else (keys,)
            partition = {column: _stable_value(value) for column, value in zip(partition_columns, key_tuple, strict=True)}
            partitions.append(
                {
                    "partition": partition,
                    "rows": int(group.shape[0]),
                    "hash": deterministic_frame_hash(group),
                }
            )
        manifest[source_name] = partitions
    return manifest


def feature_registry_hash(registry: FeatureRegistry) -> str:
    """Hash a feature registry snapshot."""
    payload = registry.as_frame().to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode()).hexdigest()


def feature_set_hash(
    features: pd.DataFrame,
    registry: FeatureRegistry,
    source_manifest: Mapping[str, object],
) -> str:
    """Hash feature values, registry metadata, and source partitions together."""
    payload = {
        "feature_values_hash": deterministic_frame_hash(features),
        "registry_hash": feature_registry_hash(registry),
        "source_manifest": source_manifest,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def freeze_training_snapshot(
    features: pd.DataFrame,
    registry: FeatureRegistry,
    source_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Return a reproducible training-dataset snapshot manifest."""
    return {
        "rows": int(features.shape[0]),
        "columns": sorted(features.columns),
        "feature_registry_hash": feature_registry_hash(registry),
        "feature_values_hash": deterministic_frame_hash(features),
        "source_manifest": source_manifest,
        "feature_set_hash": feature_set_hash(features, registry, source_manifest),
    }


def write_training_snapshot_manifest(
    features: pd.DataFrame,
    registry: FeatureRegistry,
    source_manifest: Mapping[str, object],
    output_path: Path,
) -> dict[str, object]:
    """Write a deterministic training snapshot manifest to disk."""
    manifest = freeze_training_snapshot(features, registry, source_manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def parity_report(
    pandas_features: pd.DataFrame,
    warehouse_features: pd.DataFrame,
    *,
    key_columns: tuple[str, ...],
    feature_columns: tuple[str, ...],
    tolerance: float = 1e-6,
) -> ParityReport:
    """Compare local and warehouse feature values on the same keys."""
    _raise_missing("pandas_features", pandas_features, set(key_columns).union(feature_columns))
    _raise_missing("warehouse_features", warehouse_features, set(key_columns).union(feature_columns))
    joined = pandas_features.merge(
        warehouse_features,
        on=list(key_columns),
        how="inner",
        suffixes=("_pandas", "_warehouse"),
        validate="one_to_one",
    )
    mismatched: list[str] = []
    max_abs_differences: dict[str, float] = {}
    for column in feature_columns:
        left = joined[f"{column}_pandas"]
        right = joined[f"{column}_warehouse"]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            max_abs = float((pd.to_numeric(left) - pd.to_numeric(right)).abs().max())
            max_abs_differences[column] = 0.0 if np.isnan(max_abs) else max_abs
            if max_abs_differences[column] > tolerance:
                mismatched.append(column)
        else:
            differs = left.fillna("<NULL>").astype(str) != right.fillna("<NULL>").astype(str)
            if bool(differs.any()):
                mismatched.append(column)
    status: ParityStatus = "fail" if mismatched else "pass"
    return ParityReport(status, int(joined.shape[0]), tuple(mismatched), max_abs_differences)


def _to_utc(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce")


def _raise_missing(label: str, frame: pd.DataFrame, columns: set[str]) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


def _stable_value(value: object) -> str:
    if value is None or value is pd.NA or value is pd.NaT:
        return "<NULL>"
    if isinstance(value, float | np.floating) and bool(np.isnan(value)):
        return "<NULL>"
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)
