from __future__ import annotations

import pandas as pd

from perishable_lab.deployment import (
    ExperimentDesign,
    GuardrailThresholds,
    RolloutMetrics,
    assign_experiment_groups,
    build_shadow_log,
    contamination_issues,
    default_rollout_stages,
    evaluate_guardrails,
    experiment_manifest,
    rollback_runbook,
    sample_ratio_check,
    summarize_experiment_outcomes,
    validate_telemetry,
)


def _design() -> ExperimentDesign:
    return ExperimentDesign(
        experiment_id="fresh-test-2026w03",
        unit="store",
        treatment_fraction=0.5,
        salt="stable-v1",
        baseline_start="2025-12-01",
        baseline_end="2025-12-28",
        analysis_start="2026-01-05",
        analysis_end="2026-02-01",
        minimum_detectable_effect=0.02,
    )


def test_assignment_is_deterministic() -> None:
    units = pd.DataFrame({"store_id": ["s1", "s2", "s3"], "region": ["north", "north", "south"]})

    first = assign_experiment_groups(units, _design(), unit_columns=("store_id",))
    second = assign_experiment_groups(units, _design(), unit_columns=("store_id",))

    assert first[["assignment_unit", "assignment_group", "assignment_score"]].equals(
        second[["assignment_unit", "assignment_group", "assignment_score"]]
    )


def test_shadow_log_keeps_incumbent_active() -> None:
    incumbent = pd.DataFrame({"store_id": ["s1"], "product_id": ["p1"], "order_units": [6]})
    candidate = pd.DataFrame({"store_id": ["s1"], "product_id": ["p1"], "order_units": [9]})

    log = build_shadow_log(
        incumbent,
        candidate,
        keys=("store_id", "product_id"),
        incumbent_quantity_column="order_units",
        candidate_quantity_column="order_units",
    )

    assert log.loc[0, "active_order_units"] == 6
    assert log.loc[0, "candidate_order_units"] == 9
    assert log.loc[0, "published_policy"] == "incumbent"


def test_contamination_issues_find_split_spillover_groups() -> None:
    assignments = pd.DataFrame(
        {
            "display_group": ["front-table", "front-table", "cooler"],
            "assignment_group": ["candidate", "incumbent", "candidate"],
        }
    )

    issues = contamination_issues(assignments, cluster_columns=("display_group",))

    assert issues["display_group"].tolist() == ["front-table"]


def test_sample_ratio_check_alerts_on_extreme_imbalance() -> None:
    assignments = pd.DataFrame({"assignment_group": ["candidate"] * 80 + ["incumbent"] * 20})

    check = sample_ratio_check(assignments, expected_fraction=0.5)

    assert check.status == "alert"
    assert check.reason == "sample_ratio_mismatch"


def test_validate_telemetry_reports_missing_and_null_columns() -> None:
    telemetry = pd.DataFrame(
        {
            "experiment_id": ["fresh-test-2026w03"],
            "assignment_unit": [None],
            "assignment_group": ["candidate"],
            "business_date": ["2026-01-05"],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "active_order_units": [7],
            "published_policy": ["candidate"],
        }
    )

    validation = validate_telemetry(telemetry)

    assert validation.status == "fail"
    assert "assignment_unit" in validation.null_columns
    assert "candidate_order_units" in validation.missing_columns


def test_guardrail_breach_triggers_rollback() -> None:
    metrics = RolloutMetrics(
        balanced_loss_delta=0.01,
        availability_delta=-0.05,
        waste_rate_delta=0.01,
        override_rate=0.05,
        order_volatility=0.10,
        incident_rate=0.02,
        store_fairness_gap=0.01,
    )
    thresholds = GuardrailThresholds(
        max_balanced_loss_increase=0.03,
        max_availability_drop=0.02,
        max_waste_rate_increase=0.03,
        max_override_rate=0.20,
        max_order_volatility=0.25,
        max_incident_rate=0.05,
        max_store_fairness_gap=0.05,
    )

    decision = evaluate_guardrails(metrics, thresholds)

    assert decision.status == "rollback"
    assert decision.reasons == ("availability_drop",)


def test_outcome_summary_is_reproducible_with_covariate_adjustment() -> None:
    telemetry = pd.DataFrame(
        {
            "assignment_group": ["candidate", "candidate", "incumbent", "incumbent"],
            "availability_rate": [0.96, 0.94, 0.93, 0.91],
            "waste_rate": [0.06, 0.07, 0.08, 0.09],
            "margin": [12.0, 11.0, 10.0, 9.0],
            "baseline_margin": [8.0, 7.0, 6.0, 5.0],
        }
    )

    first = summarize_experiment_outcomes(telemetry, covariate_columns=("baseline_margin",))
    second = summarize_experiment_outcomes(telemetry, covariate_columns=("baseline_margin",))

    assert first == second
    assert first["candidate_rows"] == 2
    assert first["incumbent_rows"] == 2


def test_manifest_and_runbook_are_stable() -> None:
    units = pd.DataFrame({"store_id": ["s2", "s1"]})
    assignments = assign_experiment_groups(units, _design(), unit_columns=("store_id",))

    first = experiment_manifest(_design(), assignments)
    second = experiment_manifest(_design(), assignments.sample(frac=1.0, random_state=7))
    stages = default_rollout_stages()
    runbook = rollback_runbook(stages[-1])

    assert first == second
    assert stages[0].name == "historical_replay"
    assert runbook[1] == "Set active policy to incumbent_ordering_policy"
