"""Failure analysis for forecast and replenishment degradation."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd

FailureCause = Literal[
    "missing_or_late_data",
    "product_mapping_error",
    "promotion_or_event_surprise",
    "stockout_censored_target",
    "inventory_state_error",
    "supplier_disruption",
    "shelf_life_misspecification",
    "cold_start_or_structural_break",
    "tail_undercoverage",
    "constraint_or_policy_error",
    "human_override_or_workflow_mismatch",
    "publication_system_failure",
    "unknown",
]
DiagnosticMode = Literal["real_time", "post_outcome"]
RecordLevel = Literal["row", "episode"]


CAUSE_LABELS: dict[FailureCause, str] = {
    "missing_or_late_data": "Missing or late data",
    "product_mapping_error": "Product-mapping error",
    "promotion_or_event_surprise": "Promotion or event surprise",
    "stockout_censored_target": "Stockout-censored target",
    "inventory_state_error": "Inventory-state error",
    "supplier_disruption": "Supplier disruption",
    "shelf_life_misspecification": "Shelf-life misspecification",
    "cold_start_or_structural_break": "Cold start or structural break",
    "tail_undercoverage": "Tail undercoverage",
    "constraint_or_policy_error": "Constraint or policy error",
    "human_override_or_workflow_mismatch": "Human override or workflow mismatch",
    "publication_system_failure": "Publication/system failure",
    "unknown": "Unknown",
}

CAUSE_ACTIONS: dict[FailureCause, str] = {
    "missing_or_late_data": "Add source freshness checks and quarantine late partitions before scoring.",
    "product_mapping_error": "Create a regression fixture for the identity mapping and require review for churn.",
    "promotion_or_event_surprise": "Record event availability time and add a cutoff-safe event revision test.",
    "stockout_censored_target": "Separate observed sales from latent demand and add censoring diagnostics.",
    "inventory_state_error": "Reconcile stock snapshots with delivery, sales, shrinkage, and waste ledgers.",
    "supplier_disruption": "Join supplier exception data before recommendation publication.",
    "shelf_life_misspecification": "Validate shelf-life assumptions by product, supplier, and receiving condition.",
    "cold_start_or_structural_break": "Route sparse or shifted cohorts through hierarchical fallback and monitoring.",
    "tail_undercoverage": "Calibrate intervals by segment and add coverage gates for affected cohorts.",
    "constraint_or_policy_error": "Add fixtures for pack, minimum order, storage, and display constraints.",
    "human_override_or_workflow_mismatch": "Review workflow evidence and capture structured override reasons.",
    "publication_system_failure": "Hold publication, replay the run, and add an idempotence regression fixture.",
    "unknown": "Create a minimal reproduction and collect missing source context before changing the model.",
}

PRE_OUTCOME_CAUSES: frozenset[FailureCause] = frozenset(
    {
        "missing_or_late_data",
        "product_mapping_error",
        "promotion_or_event_surprise",
        "inventory_state_error",
        "supplier_disruption",
        "shelf_life_misspecification",
        "cold_start_or_structural_break",
        "constraint_or_policy_error",
        "human_override_or_workflow_mismatch",
        "publication_system_failure",
    }
)


@dataclass(frozen=True)
class FailureSignal:
    """Candidate mechanism for one failure record."""

    cause: FailureCause
    confidence: float
    evidence: str
    impact: float


@dataclass(frozen=True)
class FailureRecord:
    """Row-level or episode-level diagnostic record."""

    record_id: str
    level: RecordLevel
    store_id: str
    product_id: str
    start_date: str
    end_date: str
    primary_cause: FailureCause
    causes: tuple[FailureSignal, ...]
    forecast_abs_error: float
    decision_cost: float
    impact_score: float
    affected_rows: int
    mechanism: str
    proposed_change: str


def diagnose_failures(
    frame: pd.DataFrame,
    *,
    mode: DiagnosticMode = "post_outcome",
) -> tuple[FailureRecord, ...]:
    """Create row-level failure records with candidate causes.

    ``real_time`` mode deliberately ignores outcome columns such as demand,
    interval misses, waste, fulfilled units, and lost sales.
    """
    required = {"date", "store_id", "product_id"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Failure analysis frame is missing columns: {missing}")

    prepared = frame.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    ordered = prepared.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)
    records: list[FailureRecord] = []
    for row_number, row in ordered.iterrows():
        signals = _signals_for_row(row, include_outcomes=mode == "post_outcome")
        primary = _primary_signal(signals)
        date = cast(pd.Timestamp, row["date"]).date().isoformat()
        store_id = str(row["store_id"])
        product_id = str(row["product_id"])
        forecast_abs_error = _forecast_abs_error(row) if mode == "post_outcome" else 0.0
        decision_cost = _decision_cost(row) if mode == "post_outcome" else _pre_outcome_decision_risk(row)
        impact_score = _row_impact(signals, forecast_abs_error, decision_cost)
        records.append(
            FailureRecord(
                record_id=f"row-{row_number:05d}",
                level="row",
                store_id=store_id,
                product_id=product_id,
                start_date=date,
                end_date=date,
                primary_cause=primary.cause,
                causes=tuple(sorted(signals, key=lambda item: (-item.confidence, item.cause))),
                forecast_abs_error=forecast_abs_error,
                decision_cost=decision_cost,
                impact_score=impact_score,
                affected_rows=1,
                mechanism=_mechanism(primary.cause),
                proposed_change=CAUSE_ACTIONS[primary.cause],
            )
        )
    return tuple(records)


def build_episode_records(row_records: tuple[FailureRecord, ...]) -> tuple[FailureRecord, ...]:
    """Aggregate row failures into deterministic store-product-cause episodes."""
    grouped: dict[tuple[str, str, FailureCause], list[FailureRecord]] = defaultdict(list)
    for record in row_records:
        if record.primary_cause != "unknown":
            grouped[(record.store_id, record.product_id, record.primary_cause)].append(record)

    episodes: list[FailureRecord] = []
    for index, ((store_id, product_id, cause), records) in enumerate(sorted(grouped.items())):
        causes = _merge_signals(records)
        start_date = min(record.start_date for record in records)
        end_date = max(record.end_date for record in records)
        forecast_abs_error = sum(record.forecast_abs_error for record in records)
        decision_cost = sum(record.decision_cost for record in records)
        impact_score = sum(record.impact_score for record in records)
        episodes.append(
            FailureRecord(
                record_id=f"episode-{index:04d}",
                level="episode",
                store_id=store_id,
                product_id=product_id,
                start_date=start_date,
                end_date=end_date,
                primary_cause=cause,
                causes=causes,
                forecast_abs_error=forecast_abs_error,
                decision_cost=decision_cost,
                impact_score=impact_score,
                affected_rows=len(records),
                mechanism=_mechanism(cause),
                proposed_change=CAUSE_ACTIONS[cause],
            )
        )
    return tuple(sorted(episodes, key=lambda item: (-item.impact_score, item.primary_cause, item.store_id, item.product_id)))


def records_to_frame(records: tuple[FailureRecord, ...]) -> pd.DataFrame:
    """Convert failure records into a flat table."""
    rows: list[dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "record_id": record.record_id,
                "level": record.level,
                "store_id": record.store_id,
                "product_id": record.product_id,
                "start_date": record.start_date,
                "end_date": record.end_date,
                "primary_cause": record.primary_cause,
                "candidate_causes": ",".join(signal.cause for signal in record.causes),
                "max_confidence": max((signal.confidence for signal in record.causes), default=0.0),
                "forecast_abs_error": record.forecast_abs_error,
                "decision_cost": record.decision_cost,
                "impact_score": record.impact_score,
                "affected_rows": record.affected_rows,
                "mechanism": record.mechanism,
                "proposed_change": record.proposed_change,
            }
        )
    return pd.DataFrame(rows)


def rank_failure_cohorts(records: tuple[FailureRecord, ...], *, top_n: int = 10) -> pd.DataFrame:
    """Rank recurring cohorts by operational impact."""
    episodes = build_episode_records(records)
    return records_to_frame(episodes[:top_n])


def paired_error_summary(records: tuple[FailureRecord, ...]) -> dict[str, int]:
    """Compare forecast error and decision error patterns."""
    high_forecast = 5.0
    high_decision = 25.0
    summary = {
        "statistically_poor_order_acceptable": 0,
        "small_forecast_error_high_decision_cost": 0,
        "both_poor": 0,
        "both_acceptable": 0,
    }
    for record in records:
        if record.level != "row":
            continue
        forecast_poor = record.forecast_abs_error >= high_forecast
        decision_poor = record.decision_cost >= high_decision
        if forecast_poor and not decision_poor:
            summary["statistically_poor_order_acceptable"] += 1
        elif not forecast_poor and decision_poor:
            summary["small_forecast_error_high_decision_cost"] += 1
        elif forecast_poor and decision_poor:
            summary["both_poor"] += 1
        else:
            summary["both_acceptable"] += 1
    return summary


def build_top_failure_report(
    row_records: tuple[FailureRecord, ...],
    *,
    top_n: int = 10,
) -> str:
    """Render a Markdown report with top cohorts and representative cases."""
    episodes = build_episode_records(row_records)
    paired = paired_error_summary(row_records)
    lines = [
        "# Failure Analysis Report",
        "",
        "Diagnostics assign candidate causes with confidence. They are evidence for investigation, not definitive blame.",
        "",
        "## Top Cohorts",
        "",
        "| Rank | Cohort | Cause | Rows | Impact | Proposed change |",
        "| ---: | --- | --- | ---: | ---: | --- |",
    ]
    for rank, record in enumerate(episodes[:top_n], start=1):
        cohort = f"{record.store_id}/{record.product_id}/{record.start_date}:{record.end_date}"
        lines.append(
            f"| {rank} | {cohort} | {CAUSE_LABELS[record.primary_cause]} | "
            f"{record.affected_rows} | {record.impact_score:.2f} | {record.proposed_change} |"
        )

    lines.extend(
        [
            "",
            "## Paired Forecast and Decision Analysis",
            "",
            f"- Statistically poor but operationally acceptable rows: {paired['statistically_poor_order_acceptable']}.",
            f"- Small forecast error with high decision cost rows: {paired['small_forecast_error_high_decision_cost']}.",
            f"- Rows poor on both views: {paired['both_poor']}.",
            f"- Rows acceptable on both views: {paired['both_acceptable']}.",
            "",
            "## Representative Cases",
            "",
        ]
    )
    for record in sorted(row_records, key=lambda item: (-item.impact_score, item.record_id))[:top_n]:
        evidence = "; ".join(signal.evidence for signal in record.causes)
        lines.extend(
            [
                f"### {record.record_id}: {record.store_id}/{record.product_id}/{record.start_date}",
                "",
                f"- Cause: {CAUSE_LABELS[record.primary_cause]}.",
                f"- Mechanism: {record.mechanism}",
                f"- Evidence: {evidence or 'No strong signal; collect more context.'}",
                f"- Proposed change: {record.proposed_change}",
                "",
            ]
        )
    return "\n".join(lines)


def root_cause_workflow() -> tuple[str, ...]:
    """Return the repeatable investigation workflow."""
    return (
        "Freeze the affected data, forecast, recommendation, and outcome partitions.",
        "Generate row diagnostics in post-outcome mode and real-time mode for comparison.",
        "Rank cohorts by operational impact, then inspect representative rows.",
        "Confirm whether each candidate cause has source evidence or only correlation.",
        "Create a regression fixture from confirmed source records and expected diagnostics.",
        "Add or adjust a data contract, monitoring gate, policy constraint, or calibration check.",
        "Close the incident only when the fixture fails before the change and passes after it.",
    )


def write_failure_analysis(
    frame: pd.DataFrame,
    output_dir: Path,
    *,
    mode: DiagnosticMode = "post_outcome",
) -> dict[str, str]:
    """Write diagnostic records, ranked cohorts, and a Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    row_records = diagnose_failures(frame, mode=mode)
    episode_records = build_episode_records(row_records)
    records_to_frame(row_records).to_csv(output_dir / "failure_records.csv", index=False)
    records_to_frame(episode_records).to_csv(output_dir / "failure_episodes.csv", index=False)
    (output_dir / "top_failure_report.md").write_text(
        build_top_failure_report(row_records),
        encoding="utf-8",
    )
    (output_dir / "root_cause_workflow.json").write_text(
        json.dumps(root_cause_workflow(), indent=2),
        encoding="utf-8",
    )
    return {
        "records": str(output_dir / "failure_records.csv"),
        "episodes": str(output_dir / "failure_episodes.csv"),
        "report": str(output_dir / "top_failure_report.md"),
        "workflow": str(output_dir / "root_cause_workflow.json"),
    }


def write_regression_fixture(
    source_frame: pd.DataFrame,
    records: tuple[FailureRecord, ...],
    output_path: Path,
    *,
    record_id: str,
) -> Path:
    """Write a minimal fixture for a confirmed incident."""
    selected = next((record for record in records if record.record_id == record_id), None)
    if selected is None:
        raise ValueError(f"Unknown record_id: {record_id}")
    keys = {
        "store_id": selected.store_id,
        "product_id": selected.product_id,
        "start_date": selected.start_date,
        "end_date": selected.end_date,
        "expected_primary_cause": selected.primary_cause,
    }
    frame = source_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    rows = frame.loc[
        (frame["store_id"].astype(str) == selected.store_id)
        & (frame["product_id"].astype(str) == selected.product_id)
        & (frame["date"] >= selected.start_date)
        & (frame["date"] <= selected.end_date)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"keys": keys, "rows": rows.to_dict(orient="records")}, indent=2, default=str),
        encoding="utf-8",
    )
    return output_path


def _signals_for_row(row: pd.Series, *, include_outcomes: bool) -> list[FailureSignal]:
    signals: list[FailureSignal] = []
    _add_if(signals, _numeric(row, "missing_source_count") > 0, "missing_or_late_data", 0.92, row, "missing_source_count")
    _add_if(signals, _numeric(row, "data_latency_hours") > 6.0, "missing_or_late_data", 0.86, row, "data_latency_hours")
    _add_if(signals, _numeric(row, "mapping_confidence", 1.0) < 0.85, "product_mapping_error", 0.88, row, "mapping_confidence")
    _add_if(signals, _bool(row, "event_surprise"), "promotion_or_event_surprise", 0.86, row, "event_surprise")
    _add_if(signals, not _bool(row, "event_known_by_cutoff", True), "promotion_or_event_surprise", 0.76, row, "event_known_by_cutoff")
    _add_if(signals, _numeric(row, "inventory_gap_units") >= 5.0, "inventory_state_error", 0.88, row, "inventory_gap_units")
    _add_if(signals, _numeric(row, "supplier_fill_rate", 1.0) < 0.90, "supplier_disruption", 0.84, row, "supplier_fill_rate")
    _add_if(signals, _bool(row, "supplier_exception"), "supplier_disruption", 0.90, row, "supplier_exception")
    expected_life = _numeric(row, "expected_shelf_life_days")
    observed_life = _numeric(row, "shelf_life_days")
    _add_if(
        signals,
        expected_life > 0.0 and observed_life > 0.0 and abs(expected_life - observed_life) >= 1.0,
        "shelf_life_misspecification",
        0.80,
        row,
        "shelf_life_days",
    )
    _add_if(signals, _bool(row, "cold_start"), "cold_start_or_structural_break", 0.78, row, "cold_start")
    _add_if(
        signals,
        _numeric(row, "structural_break_score") >= 2.5,
        "cold_start_or_structural_break",
        0.82,
        row,
        "structural_break_score",
    )
    _add_if(signals, _bool(row, "constraint_violation"), "constraint_or_policy_error", 0.93, row, "constraint_violation")
    _add_if(signals, _numeric(row, "order_constraint_gap_units") > 0.0, "constraint_or_policy_error", 0.83, row, "order_constraint_gap_units")
    override_reason = str(row.get("override_reason", "") or "")
    _add_if(
        signals,
        override_reason.strip() != "",
        "human_override_or_workflow_mismatch",
        0.78,
        row,
        "override_reason",
    )
    status = str(row.get("publication_status", "published") or "published")
    _add_if(signals, status not in {"published", "not_applicable"}, "publication_system_failure", 0.94, row, "publication_status")

    if include_outcomes:
        _add_if(signals, _bool(row, "stockout_observed"), "stockout_censored_target", 0.80, row, "stockout_observed")
        actual = _actual(row)
        upper = _upper(row)
        if actual is not None and upper is not None and actual > upper:
            signals.append(
                FailureSignal(
                    cause="tail_undercoverage",
                    confidence=min(0.95, 0.65 + (actual - upper) / max(actual, 1.0)),
                    evidence=f"actual {actual:.2f} exceeded upper interval {upper:.2f}",
                    impact=max(actual - upper, 0.0),
                )
            )

    if not include_outcomes:
        signals = [signal for signal in signals if signal.cause in PRE_OUTCOME_CAUSES]
    if not signals:
        signals.append(FailureSignal("unknown", 0.20, "no configured signal exceeded threshold", 0.0))
    return signals


def _add_if(
    signals: list[FailureSignal],
    condition: bool,
    cause: FailureCause,
    confidence: float,
    row: pd.Series,
    evidence_column: str,
) -> None:
    if condition:
        value = row.get(evidence_column)
        signals.append(
            FailureSignal(
                cause=cause,
                confidence=confidence,
                evidence=f"{evidence_column}={value}",
                impact=max(abs(_numeric(row, evidence_column)), 1.0),
            )
        )


def _numeric(row: pd.Series, column: str, default: float = 0.0) -> float:
    value = row.get(column, default)
    if value is None:
        return default
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return default
    return float(numeric)


def _bool(row: pd.Series, column: str, default: bool = False) -> bool:
    value = row.get(column, default)
    if value is None or pd.isna(value):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _actual(row: pd.Series) -> float | None:
    for column in ("actual_demand", "true_demand", "demand"):
        if column in row and pd.notna(row[column]):
            return _numeric(row, column)
    return None


def _forecast(row: pd.Series) -> float | None:
    for column in ("forecast", "q50", "forecast_median"):
        if column in row and pd.notna(row[column]):
            return _numeric(row, column)
    return None


def _upper(row: pd.Series) -> float | None:
    for column in ("interval_upper", "q90", "q95"):
        if column in row and pd.notna(row[column]):
            return _numeric(row, column)
    return None


def _forecast_abs_error(row: pd.Series) -> float:
    actual = _actual(row)
    forecast = _forecast(row)
    if actual is None or forecast is None:
        return 0.0
    return abs(actual - forecast)


def _decision_cost(row: pd.Series) -> float:
    if "decision_cost" in row and pd.notna(row["decision_cost"]):
        return _numeric(row, "decision_cost")
    if "total_cost" in row and pd.notna(row["total_cost"]):
        return _numeric(row, "total_cost")
    lost = _numeric(row, "lost_sales_units") + _numeric(row, "lost_sales")
    waste = _numeric(row, "waste_units")
    unit_margin = _numeric(row, "unit_margin", 1.0)
    unit_cost = _numeric(row, "unit_cost", 1.0)
    waste_cost = _numeric(row, "waste_cost", 0.0)
    return lost * unit_margin + waste * (unit_cost + waste_cost)


def _pre_outcome_decision_risk(row: pd.Series) -> float:
    return _numeric(row, "order_constraint_gap_units") + max(0.0, 1.0 - _numeric(row, "supplier_fill_rate", 1.0)) * 10.0


def _row_impact(signals: list[FailureSignal], forecast_abs_error: float, decision_cost: float) -> float:
    signal_impact = sum(signal.impact * signal.confidence for signal in signals if signal.cause != "unknown")
    return float(signal_impact + forecast_abs_error + decision_cost)


def _primary_signal(signals: list[FailureSignal]) -> FailureSignal:
    return max(signals, key=lambda signal: (signal.impact * signal.confidence, signal.confidence, signal.cause))


def _merge_signals(records: list[FailureRecord]) -> tuple[FailureSignal, ...]:
    by_cause: dict[FailureCause, list[FailureSignal]] = defaultdict(list)
    for record in records:
        for signal in record.causes:
            by_cause[signal.cause].append(signal)
    merged = [
        FailureSignal(
            cause=cause,
            confidence=max(signal.confidence for signal in signals),
            evidence="; ".join(sorted({signal.evidence for signal in signals})[:3]),
            impact=sum(signal.impact for signal in signals),
        )
        for cause, signals in by_cause.items()
    ]
    return tuple(sorted(merged, key=lambda signal: (-signal.impact, signal.cause)))


def _mechanism(cause: FailureCause) -> str:
    mechanisms: dict[FailureCause, str] = {
        "missing_or_late_data": "Inputs available to the scoring run may not represent the operating day.",
        "product_mapping_error": "History may be attached to the wrong product identity.",
        "promotion_or_event_surprise": "Demand changed because commercial context was unknown or revised after cutoff.",
        "stockout_censored_target": "Observed sales may be lower than latent demand due to availability.",
        "inventory_state_error": "The policy may subtract an inaccurate stock position from the order target.",
        "supplier_disruption": "Delivered units or timing may differ from the assumed replenishment path.",
        "shelf_life_misspecification": "Usable inventory life may be shorter or longer than the policy assumes.",
        "cold_start_or_structural_break": "The history distribution may not represent the current item or period.",
        "tail_undercoverage": "The realised demand landed outside the calibrated upper interval.",
        "constraint_or_policy_error": "The final quantity may violate operational constraints or policy invariants.",
        "human_override_or_workflow_mismatch": "The recommendation may miss local context or be hard to act on.",
        "publication_system_failure": "The output path may be incomplete, stale, or inconsistent.",
        "unknown": "No configured signal is strong enough to explain the degradation.",
    }
    return mechanisms[cause]


__all__ = [
    "CAUSE_ACTIONS",
    "CAUSE_LABELS",
    "FailureCause",
    "FailureRecord",
    "FailureSignal",
    "build_episode_records",
    "build_top_failure_report",
    "diagnose_failures",
    "paired_error_summary",
    "rank_failure_cohorts",
    "records_to_frame",
    "root_cause_workflow",
    "write_failure_analysis",
    "write_regression_fixture",
]
