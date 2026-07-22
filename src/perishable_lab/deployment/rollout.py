"""Experiment assignment, telemetry, and rollout controls."""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

AssignmentUnit = Literal["store", "department", "product_cluster", "time_block"]
AssignmentGroup = Literal["incumbent", "candidate"]
GateStatus = Literal["pass", "hold", "rollback"]


@dataclass(frozen=True)
class ExperimentDesign:
    """Pre-registered assignment settings for a field test."""

    experiment_id: str
    unit: AssignmentUnit
    treatment_fraction: float
    salt: str
    baseline_start: str
    baseline_end: str
    analysis_start: str
    analysis_end: str
    minimum_detectable_effect: float
    primary_metric: str = "balanced_loss"

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ValueError("experiment_id is required")
        if not 0.0 < self.treatment_fraction < 1.0:
            raise ValueError("treatment_fraction must be between zero and one")
        if self.minimum_detectable_effect <= 0:
            raise ValueError("minimum_detectable_effect must be positive")


@dataclass(frozen=True)
class SampleRatioCheck:
    """Observed assignment balance against the registered allocation."""

    expected_fraction: float
    observed_fraction: float
    count: int
    z_score: float
    status: Literal["pass", "alert"]
    reason: str | None = None


@dataclass(frozen=True)
class TelemetryContract:
    """Required columns emitted for each live recommendation."""

    required_columns: tuple[str, ...] = (
        "experiment_id",
        "assignment_unit",
        "assignment_group",
        "business_date",
        "store_id",
        "product_id",
        "incumbent_order_units",
        "candidate_order_units",
        "active_order_units",
        "published_policy",
        "availability_rate",
        "waste_rate",
        "revenue",
        "margin",
        "override_reason",
        "incident_count",
    )
    non_null_columns: tuple[str, ...] = (
        "experiment_id",
        "assignment_unit",
        "assignment_group",
        "business_date",
        "store_id",
        "product_id",
        "active_order_units",
        "published_policy",
    )


@dataclass(frozen=True)
class TelemetryValidation:
    """Validation result for rollout telemetry."""

    status: Literal["pass", "fail"]
    missing_columns: tuple[str, ...]
    null_columns: tuple[str, ...]


@dataclass(frozen=True)
class GuardrailThresholds:
    """Operational limits that stop or pause rollout."""

    max_balanced_loss_increase: float
    max_availability_drop: float
    max_waste_rate_increase: float
    max_override_rate: float
    max_order_volatility: float
    max_incident_rate: float
    max_store_fairness_gap: float


@dataclass(frozen=True)
class RolloutMetrics:
    """Observed comparison between candidate and incumbent operations."""

    balanced_loss_delta: float
    availability_delta: float
    waste_rate_delta: float
    override_rate: float
    order_volatility: float
    incident_rate: float
    store_fairness_gap: float


@dataclass(frozen=True)
class GuardrailDecision:
    """Decision with concrete reasons for pass, hold, or rollback."""

    status: GateStatus
    reasons: tuple[str, ...]
    metrics: RolloutMetrics


@dataclass(frozen=True)
class RolloutStage:
    """Evidence gate for one rollout stage."""

    name: str
    traffic_fraction: float
    entry_evidence: tuple[str, ...]
    exit_evidence: tuple[str, ...]
    stop_authority: tuple[str, ...]
    fallback_policy: str


def assignment_score(*parts: object, salt: str) -> float:
    """Map an assignment key to a reproducible score in [0, 1)."""
    key = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(f"{salt}|{key}".encode()).hexdigest()
    return int(digest[:16], 16) / float(16**16)


def assign_experiment_groups(
    units: pd.DataFrame,
    design: ExperimentDesign,
    *,
    unit_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Assign units to incumbent or candidate groups with stable hashing."""
    missing = [column for column in unit_columns if column not in units.columns]
    if missing:
        raise ValueError(f"Missing assignment columns: {missing}")
    assigned = units.copy(deep=True)
    scores = assigned.apply(lambda row: assignment_score(*(row[column] for column in unit_columns), salt=design.salt), axis=1)
    assigned["experiment_id"] = design.experiment_id
    assigned["assignment_unit"] = assigned[list(unit_columns)].astype(str).agg("|".join, axis=1)
    assigned["assignment_score"] = scores.astype(float)
    assigned["assignment_group"] = np.where(
        assigned["assignment_score"] < design.treatment_fraction,
        "candidate",
        "incumbent",
    )
    return assigned


def sample_ratio_check(
    assignments: pd.DataFrame,
    *,
    expected_fraction: float,
    group_column: str = "assignment_group",
    candidate_value: str = "candidate",
    z_threshold: float = 3.0,
) -> SampleRatioCheck:
    """Alert when realised assignment balance differs from registration."""
    if assignments.empty:
        return SampleRatioCheck(expected_fraction, 0.0, 0, 0.0, "alert", "no_assignments")
    observed = float((assignments[group_column] == candidate_value).mean())
    count = int(assignments.shape[0])
    variance = max(count * expected_fraction * (1.0 - expected_fraction), 1e-12)
    z_score = (observed * count - expected_fraction * count) / math.sqrt(variance)
    status: Literal["pass", "alert"] = "alert" if abs(z_score) > z_threshold else "pass"
    reason = "sample_ratio_mismatch" if status == "alert" else None
    return SampleRatioCheck(expected_fraction, observed, count, float(z_score), status, reason)


def contamination_issues(
    assignments: pd.DataFrame,
    *,
    cluster_columns: tuple[str, ...],
    group_column: str = "assignment_group",
) -> pd.DataFrame:
    """Return spillover clusters assigned to more than one group."""
    missing = [column for column in (*cluster_columns, group_column) if column not in assignments.columns]
    if missing:
        raise ValueError(f"Missing contamination columns: {missing}")
    grouped = (
        assignments.groupby(list(cluster_columns), dropna=False)[group_column]
        .nunique()
        .reset_index(name="assignment_group_count")
    )
    return grouped[grouped["assignment_group_count"] > 1].reset_index(drop=True)


def validate_telemetry(frame: pd.DataFrame, contract: TelemetryContract | None = None) -> TelemetryValidation:
    """Validate that field-test telemetry is complete enough for decisions."""
    active_contract = contract or TelemetryContract()
    missing = tuple(column for column in active_contract.required_columns if column not in frame.columns)
    null_columns = tuple(
        column
        for column in active_contract.non_null_columns
        if column in frame.columns and bool(frame[column].isna().any())
    )
    status: Literal["pass", "fail"] = "fail" if missing or null_columns else "pass"
    return TelemetryValidation(status, missing, null_columns)


def evaluate_guardrails(metrics: RolloutMetrics, thresholds: GuardrailThresholds) -> GuardrailDecision:
    """Evaluate operational guardrails and choose pass, hold, or rollback."""
    rollback_reasons: list[str] = []
    hold_reasons: list[str] = []
    if metrics.availability_delta < -thresholds.max_availability_drop:
        rollback_reasons.append("availability_drop")
    if metrics.waste_rate_delta > thresholds.max_waste_rate_increase:
        rollback_reasons.append("waste_increase")
    if metrics.incident_rate > thresholds.max_incident_rate:
        rollback_reasons.append("incident_rate")
    if metrics.balanced_loss_delta > thresholds.max_balanced_loss_increase:
        hold_reasons.append("balanced_loss")
    if metrics.override_rate > thresholds.max_override_rate:
        hold_reasons.append("override_rate")
    if metrics.order_volatility > thresholds.max_order_volatility:
        hold_reasons.append("order_volatility")
    if metrics.store_fairness_gap > thresholds.max_store_fairness_gap:
        hold_reasons.append("store_fairness_gap")
    if rollback_reasons:
        return GuardrailDecision("rollback", tuple(rollback_reasons), metrics)
    if hold_reasons:
        return GuardrailDecision("hold", tuple(hold_reasons), metrics)
    return GuardrailDecision("pass", (), metrics)


def default_rollout_stages() -> tuple[RolloutStage, ...]:
    """Return the staged evidence path from replay to full rollout."""
    fallback = "incumbent_ordering_policy"
    return (
        RolloutStage(
            "historical_replay",
            0.0,
            ("frozen input snapshots", "known incumbent actions", "simulator validation passed"),
            ("offline estimate passes guardrails", "sensitivity bounds remain acceptable"),
            ("experiment owner", "operations lead"),
            fallback,
        ),
        RolloutStage(
            "shadow",
            0.0,
            ("telemetry contract deployed", "daily comparison dashboard available"),
            ("no missing critical telemetry", "candidate decisions generated on schedule"),
            ("experiment owner", "operations lead", "platform owner"),
            fallback,
        ),
        RolloutStage(
            "human_review",
            0.0,
            ("shadow guardrails passed", "review workflow staffed"),
            ("accepted recommendations meet threshold", "override reasons reviewed weekly"),
            ("store operations lead", "experiment owner"),
            fallback,
        ),
        RolloutStage(
            "limited_pilot",
            0.05,
            ("store roster approved", "rollback runbook rehearsed"),
            ("availability and waste guardrails pass", "incident rate within limit"),
            ("operations lead", "commercial owner", "on-call owner"),
            fallback,
        ),
        RolloutStage(
            "field_test",
            0.50,
            ("assignment table published", "baseline period locked", "power check approved"),
            ("primary estimand passes", "no sample-ratio alert", "clustered uncertainty reported"),
            ("experiment owner", "analytics owner", "operations lead"),
            fallback,
        ),
        RolloutStage(
            "progressive_rollout",
            1.0,
            ("field-test decision log approved", "support team ready"),
            ("all guardrails pass at each ramp", "no unresolved incidents"),
            ("operations lead", "commercial owner", "platform owner"),
            fallback,
        ),
    )


def build_shadow_log(
    incumbent: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    keys: tuple[str, ...],
    incumbent_quantity_column: str,
    candidate_quantity_column: str,
) -> pd.DataFrame:
    """Compare candidate decisions while publishing only incumbent quantities."""
    merged = incumbent.merge(candidate, on=list(keys), suffixes=("_incumbent", "_candidate"), validate="one_to_one")
    incumbent_column = f"{incumbent_quantity_column}_incumbent"
    candidate_column = f"{candidate_quantity_column}_candidate"
    merged["incumbent_order_units"] = merged[incumbent_column]
    merged["candidate_order_units"] = merged[candidate_column]
    merged["active_order_units"] = merged["incumbent_order_units"]
    merged["published_policy"] = "incumbent"
    merged["candidate_delta_units"] = merged["candidate_order_units"] - merged["incumbent_order_units"]
    return merged


def summarize_experiment_outcomes(
    telemetry: pd.DataFrame,
    *,
    group_column: str = "assignment_group",
    candidate_value: str = "candidate",
    incumbent_value: str = "incumbent",
    covariate_columns: tuple[str, ...] = (),
) -> dict[str, object]:
    """Return a deterministic field-test summary using package functions only."""
    required = {"availability_rate", "waste_rate", "margin", group_column}
    missing = required.difference(telemetry.columns)
    if missing:
        raise ValueError(f"Missing outcome columns: {sorted(missing)}")
    frame = telemetry.copy(deep=True)
    frame["balanced_loss"] = (1.0 - frame["availability_rate"]) + frame["waste_rate"]
    if covariate_columns:
        frame = _residualize(frame, ("balanced_loss", "availability_rate", "waste_rate", "margin"), covariate_columns)
    candidate = frame[frame[group_column] == candidate_value]
    incumbent = frame[frame[group_column] == incumbent_value]
    if candidate.empty or incumbent.empty:
        raise ValueError("Both candidate and incumbent observations are required")
    return {
        "rows": int(frame.shape[0]),
        "candidate_rows": int(candidate.shape[0]),
        "incumbent_rows": int(incumbent.shape[0]),
        "balanced_loss_delta": float(candidate["balanced_loss"].mean() - incumbent["balanced_loss"].mean()),
        "availability_delta": float(candidate["availability_rate"].mean() - incumbent["availability_rate"].mean()),
        "waste_rate_delta": float(candidate["waste_rate"].mean() - incumbent["waste_rate"].mean()),
        "margin_delta": float(candidate["margin"].mean() - incumbent["margin"].mean()),
    }


def rollback_runbook(stage: RolloutStage) -> tuple[str, ...]:
    """Return deterministic rollback steps for active recommendations."""
    return (
        f"Freeze ramp at stage {stage.name}",
        f"Set active policy to {stage.fallback_policy}",
        "Republish incumbent quantities for pending order cycles",
        "Notify store operations and support owners",
        "Archive decision log, assignment table, telemetry snapshot, and guardrail report",
    )


def _residualize(frame: pd.DataFrame, outcome_columns: tuple[str, ...], covariate_columns: tuple[str, ...]) -> pd.DataFrame:
    adjusted = frame.copy(deep=True)
    covariates = adjusted[list(covariate_columns)].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(adjusted)), covariates])
    for outcome_column in outcome_columns:
        outcome = adjusted[outcome_column].to_numpy(dtype=float)
        coefficients = np.linalg.lstsq(design, outcome, rcond=None)[0]
        fitted = design @ coefficients
        adjusted[outcome_column] = outcome - fitted + float(outcome.mean())
    return adjusted


def experiment_manifest(design: ExperimentDesign, assignments: pd.DataFrame) -> dict[str, object]:
    """Create a reproducible manifest for assignment publication."""
    payload = assignments.sort_values("assignment_unit")[
        ["experiment_id", "assignment_unit", "assignment_group", "assignment_score"]
    ].to_csv(index=False)
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "design": asdict(design),
        "assignment_rows": int(assignments.shape[0]),
        "assignment_checksum": checksum,
    }
