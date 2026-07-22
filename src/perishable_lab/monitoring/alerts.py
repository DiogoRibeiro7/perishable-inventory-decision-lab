"""Alert rules, structured logs, fallback decisions, and incident replay."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["info", "warning", "page", "critical"]
AlertStatus = Literal["firing", "suppressed", "resolved"]
ThresholdDirection = Literal["above", "below", "equal"]
FallbackAction = Literal["none", "hold_publication", "previous_valid_batch", "safe_incumbent_policy", "manual_review"]


@dataclass(frozen=True)
class AlertRule:
    """Alert configuration with ownership, threshold, and recovery semantics."""

    alert_id: str
    layer: str
    metric: str
    severity: Severity
    owner: str
    threshold: float
    direction: ThresholdDirection
    minimum_sample: int
    deduplication_key: str
    context_links: tuple[str, ...]
    safe_fallback: FallbackAction
    closure_condition: str
    automatic_rollback: bool = False

    def __post_init__(self) -> None:
        if self.minimum_sample < 1:
            raise ValueError("minimum_sample must be positive")
        if self.automatic_rollback and self.safe_fallback not in {
            "previous_valid_batch",
            "safe_incumbent_policy",
        }:
            raise ValueError("automatic rollback requires a reversible fallback")


@dataclass(frozen=True)
class AlertEvaluation:
    """Evaluated alert rule outcome."""

    alert_id: str
    status: AlertStatus
    severity: Severity
    owner: str
    metric: str
    observed_value: float | None
    threshold: float
    sample_size: int
    deduplication_key: str
    context_links: tuple[str, ...]
    safe_fallback: FallbackAction
    closure_condition: str
    reason: str


@dataclass(frozen=True)
class StructuredLogEvent:
    """Immutable structured event used for incident replay."""

    event_id: str
    timestamp_utc: str
    run_id: str
    event_type: str
    payload: dict[str, object]
    previous_event_hash: str | None = None

    def event_hash(self) -> str:
        """Return a stable hash for the log event and predecessor link."""
        payload = {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "run_id": self.run_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "previous_event_hash": self.previous_event_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class FallbackDecision:
    """Deterministic fallback action selected from firing alerts."""

    action: FallbackAction
    reasons: tuple[str, ...]
    automatic_rollback: bool


@dataclass(frozen=True)
class IncidentReplay:
    """Reconstructed incident timeline from immutable logs."""

    run_id: str
    events: tuple[StructuredLogEvent, ...]
    final_alerts: tuple[str, ...]
    chain_valid: bool


def default_alert_rules() -> tuple[AlertRule, ...]:
    """Return alert rules across data, model, decision, and system layers."""
    return (
        AlertRule(
            "stale_sales_data",
            "data",
            "sales_freshness_hours",
            "page",
            "data-oncall",
            6.0,
            "above",
            100,
            "retailer:business_date:data",
            ("dashboard:data_freshness", "runbook:stale_sales_data"),
            "hold_publication",
            "sales freshness returns below six hours for the affected date",
        ),
        AlertRule(
            "broken_product_mapping",
            "data",
            "mapping_failure_rate",
            "critical",
            "data-oncall",
            0.02,
            "above",
            100,
            "retailer:business_date:mapping",
            ("dashboard:identity", "runbook:broken_product_mapping"),
            "safe_incumbent_policy",
            "mapping failures fall below two percent and identity diff is approved",
            automatic_rollback=True,
        ),
        AlertRule(
            "promotion_feed_outage",
            "data",
            "promotion_feed_age_hours",
            "warning",
            "commercial-oncall",
            12.0,
            "above",
            50,
            "retailer:promotion_feed",
            ("dashboard:events", "runbook:promotion_feed_outage"),
            "manual_review",
            "promotion feed catches up and revised feature snapshot is published",
        ),
        AlertRule(
            "invalid_inventory_snapshots",
            "data",
            "invalid_stock_snapshot_rate",
            "critical",
            "inventory-oncall",
            0.01,
            "above",
            100,
            "retailer:business_date:inventory",
            ("dashboard:inventory", "runbook:invalid_inventory_snapshots"),
            "safe_incumbent_policy",
            "invalid snapshot rate is below one percent for two runs",
            automatic_rollback=True,
        ),
        AlertRule(
            "model_artifact_corruption",
            "model",
            "artifact_hash_mismatch",
            "critical",
            "platform-oncall",
            1.0,
            "equal",
            1,
            "retailer:model_version",
            ("dashboard:model_load", "runbook:model_artifact_corruption"),
            "previous_valid_batch",
            "artifact hash matches manifest after clean redeploy",
            automatic_rollback=True,
        ),
        AlertRule(
            "forecast_undercoverage",
            "model",
            "coverage_rate",
            "page",
            "forecasting-oncall",
            0.75,
            "below",
            500,
            "retailer:business_date:coverage",
            ("dashboard:forecast_quality", "runbook:forecast_undercoverage"),
            "manual_review",
            "coverage returns above threshold after outcomes are complete",
        ),
        AlertRule(
            "supplier_disruption",
            "decision",
            "supplier_exception_rate",
            "page",
            "operations-oncall",
            0.08,
            "above",
            50,
            "retailer:supplier:business_date",
            ("dashboard:supplier", "runbook:supplier_disruption"),
            "manual_review",
            "supplier exceptions return below threshold and store comms are sent",
        ),
        AlertRule(
            "partial_warehouse_write",
            "system",
            "partition_completeness_rate",
            "critical",
            "platform-oncall",
            1.0,
            "below",
            1,
            "retailer:business_date:publication",
            ("dashboard:publication", "runbook:partial_warehouse_write"),
            "previous_valid_batch",
            "all expected partitions are written and active pointer is unchanged",
            automatic_rollback=True,
        ),
        AlertRule(
            "cloud_run_timeout",
            "system",
            "job_timeout_count",
            "page",
            "platform-oncall",
            0.0,
            "above",
            1,
            "retailer:job:business_date",
            ("dashboard:jobs", "runbook:cloud_run_timeout"),
            "hold_publication",
            "job succeeds with the same deterministic job id",
        ),
        AlertRule(
            "airflow_retry_storm",
            "system",
            "retry_count",
            "page",
            "platform-oncall",
            5.0,
            "above",
            1,
            "retailer:workflow:business_date",
            ("dashboard:workflow", "runbook:airflow_retry_storm"),
            "hold_publication",
            "retry count stops increasing and all downstream tasks are reconciled",
        ),
        AlertRule(
            "bad_policy_version",
            "decision",
            "policy_version_mismatch",
            "critical",
            "decision-oncall",
            1.0,
            "equal",
            1,
            "retailer:business_date:policy",
            ("dashboard:publication", "runbook:bad_policy_version"),
            "previous_valid_batch",
            "active pointer is reverted and policy allow-list is corrected",
            automatic_rollback=True,
        ),
    )


def evaluate_alerts(
    metrics: Mapping[str, float | int | None],
    sample_sizes: Mapping[str, int],
    rules: tuple[AlertRule, ...] | None = None,
) -> tuple[AlertEvaluation, ...]:
    """Evaluate alert rules with minimum-sample suppression."""
    active_rules = rules or default_alert_rules()
    evaluations: list[AlertEvaluation] = []
    for rule in active_rules:
        sample_size = int(sample_sizes.get(rule.metric, 0))
        value = metrics.get(rule.metric)
        observed = None if value is None else float(value)
        if sample_size < rule.minimum_sample:
            status: AlertStatus = "suppressed"
            reason = "minimum_sample_not_met"
        elif observed is None:
            status = "firing"
            reason = "metric_missing"
        elif _threshold_breached(observed, rule.threshold, rule.direction):
            status = "firing"
            reason = "threshold_breached"
        else:
            status = "resolved"
            reason = "within_threshold"
        evaluations.append(
            AlertEvaluation(
                alert_id=rule.alert_id,
                status=status,
                severity=rule.severity,
                owner=rule.owner,
                metric=rule.metric,
                observed_value=observed,
                threshold=rule.threshold,
                sample_size=sample_size,
                deduplication_key=rule.deduplication_key,
                context_links=rule.context_links,
                safe_fallback=rule.safe_fallback,
                closure_condition=rule.closure_condition,
                reason=reason,
            )
        )
    return tuple(evaluations)


def fallback_decision(
    evaluations: tuple[AlertEvaluation, ...],
    rules: tuple[AlertRule, ...] | None = None,
) -> FallbackDecision:
    """Choose the strongest fallback required by firing alerts."""
    active_rules = {rule.alert_id: rule for rule in (rules or default_alert_rules())}
    firing = [evaluation for evaluation in evaluations if evaluation.status == "firing"]
    if not firing:
        return FallbackDecision("none", (), False)
    rank: dict[FallbackAction, int] = {
        "none": 0,
        "manual_review": 1,
        "hold_publication": 2,
        "previous_valid_batch": 3,
        "safe_incumbent_policy": 4,
    }
    action = max((evaluation.safe_fallback for evaluation in firing), key=lambda item: rank[item])
    automatic = any(active_rules[evaluation.alert_id].automatic_rollback for evaluation in firing)
    return FallbackDecision(action, tuple(evaluation.alert_id for evaluation in firing), automatic)


def structured_log(
    *,
    timestamp_utc: str,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
    previous_event_hash: str | None = None,
) -> StructuredLogEvent:
    """Create a stable structured log event."""
    event_payload = json.dumps(
        {
            "timestamp_utc": timestamp_utc,
            "run_id": run_id,
            "event_type": event_type,
            "payload": payload,
            "previous_event_hash": previous_event_hash,
        },
        sort_keys=True,
        default=str,
    )
    event_id = hashlib.sha256(event_payload.encode()).hexdigest()[:16]
    return StructuredLogEvent(event_id, timestamp_utc, run_id, event_type, payload, previous_event_hash)


def evaluation_logs(
    evaluations: tuple[AlertEvaluation, ...],
    *,
    timestamp_utc: str,
    run_id: str,
) -> tuple[StructuredLogEvent, ...]:
    """Convert alert evaluations into linked immutable log events."""
    events: list[StructuredLogEvent] = []
    previous_hash: str | None = None
    for evaluation in evaluations:
        event = structured_log(
            timestamp_utc=timestamp_utc,
            run_id=run_id,
            event_type="alert_evaluation",
            payload=asdict(evaluation),
            previous_event_hash=previous_hash,
        )
        previous_hash = event.event_hash()
        events.append(event)
    return tuple(events)


def replay_incident(events: tuple[StructuredLogEvent, ...], *, run_id: str) -> IncidentReplay:
    """Replay alert state from immutable structured logs."""
    selected = tuple(event for event in events if event.run_id == run_id)
    final_alerts: list[str] = []
    previous_hash: str | None = None
    chain_valid = True
    for event in selected:
        if event.previous_event_hash != previous_hash:
            chain_valid = False
        previous_hash = event.event_hash()
        if event.event_type == "alert_evaluation" and event.payload.get("status") == "firing":
            final_alerts.append(str(event.payload["alert_id"]))
    return IncidentReplay(run_id, selected, tuple(final_alerts), chain_valid)


def dashboard_spec() -> dict[str, tuple[str, ...]]:
    """Return dashboard panels grouped by observability layer."""
    return {
        "data": (
            "freshness by source",
            "completeness by partition",
            "duplicate keys",
            "revision rate",
            "schema changes",
            "mapping churn",
            "stock anomalies",
        ),
        "model": (
            "artifact load status",
            "version allow-list",
            "latency",
            "distribution drift",
            "forecast bias",
            "coverage after outcomes",
            "fallback rate",
        ),
        "decision": (
            "missing recommendations",
            "constraint violations",
            "order jumps",
            "override rate",
            "fill rate",
            "waste",
            "stockouts",
            "supplier exceptions",
        ),
        "system": (
            "job status",
            "retries",
            "partition completeness",
            "storage writes",
            "publication state",
            "cost",
            "SLA",
        ),
    }


def service_level_objectives() -> tuple[dict[str, object], ...]:
    """Return service-level objectives for daily operation."""
    return (
        {"name": "daily_publication", "target": 0.99, "window": "30d", "measurement": "complete batch published before store cutoff"},
        {"name": "data_freshness", "target": 0.995, "window": "30d", "measurement": "core data available within freshness threshold"},
        {"name": "rollback_readiness", "target": 1.0, "window": "30d", "measurement": "previous valid batch exists for every active batch"},
        {"name": "alert_noise", "target": 0.95, "window": "30d", "measurement": "page alerts meet minimum sample and dedup rules"},
    )


def game_day_script() -> tuple[str, ...]:
    """Return deterministic drill steps for operational readiness."""
    return (
        "Freeze publication for the drill retailer and date",
        "Inject stale sales data into the metrics fixture",
        "Confirm stale-sales alert fires once after minimum sample is met",
        "Activate hold-publication fallback",
        "Replay logs and verify the event hash chain",
        "Restore healthy metrics and confirm closure condition",
        "Record impact, detection time, fallback action, and recovery time",
    )


def _threshold_breached(value: float, threshold: float, direction: ThresholdDirection) -> bool:
    if direction == "above":
        return value > threshold
    if direction == "below":
        return value < threshold
    return value == threshold
