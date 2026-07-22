from __future__ import annotations

from dataclasses import asdict

from perishable_lab.monitoring import (
    dashboard_spec,
    default_alert_rules,
    evaluate_alerts,
    evaluation_logs,
    fallback_decision,
    game_day_script,
    replay_incident,
    service_level_objectives,
)


def _healthy_metrics() -> dict[str, float]:
    return {
        "sales_freshness_hours": 1.0,
        "mapping_failure_rate": 0.0,
        "promotion_feed_age_hours": 1.0,
        "invalid_stock_snapshot_rate": 0.0,
        "artifact_hash_mismatch": 0.0,
        "coverage_rate": 0.90,
        "supplier_exception_rate": 0.0,
        "partition_completeness_rate": 1.0,
        "job_timeout_count": 0.0,
        "retry_count": 0.0,
        "policy_version_mismatch": 0.0,
    }


def _samples() -> dict[str, int]:
    return {
        "sales_freshness_hours": 200,
        "mapping_failure_rate": 200,
        "promotion_feed_age_hours": 80,
        "invalid_stock_snapshot_rate": 200,
        "artifact_hash_mismatch": 1,
        "coverage_rate": 800,
        "supplier_exception_rate": 80,
        "partition_completeness_rate": 1,
        "job_timeout_count": 1,
        "retry_count": 1,
        "policy_version_mismatch": 1,
    }


def test_every_default_alert_branch_fires_when_metric_breaches() -> None:
    metrics = {
        "sales_freshness_hours": 9.0,
        "mapping_failure_rate": 0.03,
        "promotion_feed_age_hours": 13.0,
        "invalid_stock_snapshot_rate": 0.02,
        "artifact_hash_mismatch": 1.0,
        "coverage_rate": 0.60,
        "supplier_exception_rate": 0.10,
        "partition_completeness_rate": 0.75,
        "job_timeout_count": 1.0,
        "retry_count": 6.0,
        "policy_version_mismatch": 1.0,
    }

    evaluations = evaluate_alerts(metrics, _samples())

    assert {evaluation.status for evaluation in evaluations} == {"firing"}
    assert {evaluation.alert_id for evaluation in evaluations} == {
        rule.alert_id for rule in default_alert_rules()
    }


def test_alert_suppression_avoids_noisy_small_samples() -> None:
    metrics = _healthy_metrics()
    metrics["coverage_rate"] = 0.10
    samples = _samples()
    samples["coverage_rate"] = 10

    evaluation = next(item for item in evaluate_alerts(metrics, samples) if item.alert_id == "forecast_undercoverage")

    assert evaluation.status == "suppressed"
    assert evaluation.reason == "minimum_sample_not_met"


def test_recovery_resolves_alerts_and_fallback_is_none() -> None:
    evaluations = evaluate_alerts(_healthy_metrics(), _samples())
    decision = fallback_decision(evaluations)

    assert {evaluation.status for evaluation in evaluations} == {"resolved"}
    assert decision.action == "none"
    assert not decision.automatic_rollback


def test_fallback_activation_selects_strongest_action() -> None:
    metrics = _healthy_metrics()
    metrics["mapping_failure_rate"] = 0.03
    metrics["sales_freshness_hours"] = 8.0

    decision = fallback_decision(evaluate_alerts(metrics, _samples()))

    assert decision.action == "safe_incumbent_policy"
    assert decision.automatic_rollback
    assert decision.reasons == ("stale_sales_data", "broken_product_mapping")


def test_structured_logs_replay_incident_from_immutable_chain() -> None:
    metrics = _healthy_metrics()
    metrics["partition_completeness_rate"] = 0.5
    evaluations = evaluate_alerts(metrics, _samples())

    logs = evaluation_logs(evaluations, timestamp_utc="2026-01-05T07:00:00Z", run_id="run-1")
    replay = replay_incident(logs, run_id="run-1")

    assert replay.chain_valid
    assert replay.final_alerts == ("partial_warehouse_write",)
    assert logs[0].event_hash() == logs[1].previous_event_hash


def test_replay_detects_tampered_chain() -> None:
    metrics = _healthy_metrics()
    metrics["job_timeout_count"] = 1.0
    logs = list(evaluation_logs(evaluate_alerts(metrics, _samples()), timestamp_utc="2026-01-05T07:00:00Z", run_id="run-2"))
    broken = logs[1]
    logs[1] = type(broken)(
        event_id=broken.event_id,
        timestamp_utc=broken.timestamp_utc,
        run_id=broken.run_id,
        event_type=broken.event_type,
        payload=broken.payload,
        previous_event_hash="bad-link",
    )

    replay = replay_incident(tuple(logs), run_id="run-2")

    assert not replay.chain_valid
    assert "cloud_run_timeout" in replay.final_alerts


def test_operator_specs_include_required_sections() -> None:
    dashboards = dashboard_spec()
    objectives = service_level_objectives()
    drill = game_day_script()
    first_rule = asdict(default_alert_rules()[0])

    assert "data" in dashboards
    assert "publication state" in dashboards["system"]
    assert objectives[0]["name"] == "daily_publication"
    assert drill[0] == "Freeze publication for the drill retailer and date"
    assert {"severity", "owner", "threshold", "minimum_sample", "safe_fallback", "closure_condition"}.issubset(first_rule)
