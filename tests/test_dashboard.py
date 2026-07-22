from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.dashboard import (
    DashboardMetricError,
    alert_drilldown_links,
    apply_dashboard_filters,
    apply_row_access,
    assert_aggregate_matches_drilldown,
    build_dashboard_demo_data,
    build_store_drilldown,
    compute_dashboard_metrics,
    default_metric_dictionary,
    harmed_segments,
    safe_divide,
    semantic_layer_spec,
)
from perishable_lab.inventory.simulator import summarise_simulation


def test_metric_definitions_match_package_calculations() -> None:
    simulated = pd.DataFrame(
        {
            "demand": [10, 10],
            "fulfilled": [9, 8],
            "order_quantity": [12, 10],
            "arrival": [0, 0],
            "waste_units": [1, 2],
            "lost_sales": [1, 2],
            "ending_inventory": [3, 1],
            "total_cost": [5.0, 6.0],
        }
    )
    summary = summarise_simulation(simulated, "policy")
    dashboard_input = build_dashboard_demo_data().iloc[:2].copy(deep=True)
    dashboard_input["demand_units"] = [10, 10]
    dashboard_input["fulfilled_units"] = [9, 8]
    dashboard_input["ordered_units"] = [12, 10]
    dashboard_input["waste_units"] = [1, 2]
    metrics = compute_dashboard_metrics(dashboard_input)
    waste = metrics[metrics["metric"] == "waste_rate"].iloc[0]
    availability = metrics[metrics["metric"] == "availability_rate"].iloc[0]

    assert waste["value"] == summary["waste_rate"]
    assert availability["value"] == summary["fill_rate"]


def test_denominator_edge_cases_are_explicit() -> None:
    assert safe_divide(5.0, 0.0) == 0.0
    data = build_dashboard_demo_data().iloc[:1].copy(deep=True)
    data["ordered_units"] = 0
    data["waste_units"] = 3

    metrics = compute_dashboard_metrics(data)
    waste = metrics[metrics["metric"] == "waste_rate"].iloc[0]

    assert waste["value"] == 0.0
    assert waste["denominator"] == 0.0
    assert pd.isna(waste["uncertainty_low"])


def test_late_outcomes_are_excluded_while_leading_metrics_remain() -> None:
    data = build_dashboard_demo_data().iloc[:4].copy(deep=True)
    data["outcome_available_at"] = ["2026-01-03T00:00:00", "2026-01-04T00:00:00", "2026-02-01T00:00:00", "2026-02-01T00:00:00"]

    metrics = compute_dashboard_metrics(data, as_of="2026-01-04T00:00:00Z")
    waste = metrics[metrics["metric"] == "waste_rate"].iloc[0]
    acceptance = metrics[metrics["metric"] == "acceptance_rate"].iloc[0]

    assert waste["sample_size"] == 2
    assert acceptance["sample_size"] == 4


def test_filters_and_row_access_limit_rows() -> None:
    data = build_dashboard_demo_data()

    filtered = apply_dashboard_filters(data, stores=("S001",), products=("P001",))
    accessible = apply_row_access(data, allowed_store_ids=("S002",))

    assert set(filtered["store_id"]) == {"S001"}
    assert set(filtered["product_id"]) == {"P001"}
    assert set(accessible["store_id"]) == {"S002"}
    with pytest.raises(DashboardMetricError, match="allowed_store_ids"):
        apply_row_access(data, allowed_store_ids=())


def test_aggregate_matches_drilldown_totals() -> None:
    data = build_dashboard_demo_data()
    aggregate = compute_dashboard_metrics(data)
    drilldown = compute_dashboard_metrics(data, group_columns=("store_id",))

    assert_aggregate_matches_drilldown(aggregate, drilldown, metric="waste_rate")


def test_harmed_segments_show_hidden_degradation() -> None:
    data = build_dashboard_demo_data()
    metrics = compute_dashboard_metrics(data, group_columns=("store_id",))

    harmed = harmed_segments(
        metrics,
        metric="availability_rate",
        segment_columns=("store_id",),
        threshold=0.95,
        direction="below",
    )

    assert "S003" in harmed["store_id"].tolist()


def test_drilldown_and_alert_links_explain_action() -> None:
    data = build_dashboard_demo_data()
    drilldown = build_store_drilldown(data, store_id="S001", product_id="P001")
    links = alert_drilldown_links(("stale_sales_data",))

    assert drilldown.columns.tolist() == [
        "business_date",
        "store_id",
        "product_id",
        "demand_units",
        "actual_sales",
        "waste_units",
        "stock_belief_units",
        "pending_order_units",
        "shelf_life_cohorts",
        "forecast_p05",
        "forecast_p50",
        "forecast_p95",
        "recommended_order_quantity",
        "recommendation_explanation",
        "override_reason",
    ]
    assert links["stale_sales_data"]["runbook"] == "docs/OBSERVABILITY_RUNBOOK.md"


def test_semantic_layer_has_denominators_and_access_levels() -> None:
    fields = semantic_layer_spec()
    metrics = default_metric_dictionary()

    assert {field.access_level for field in fields} == {"portfolio", "store", "restricted"}
    assert all(metric.denominator for metric in metrics)
    assert all(metric.runbook for metric in metrics)
