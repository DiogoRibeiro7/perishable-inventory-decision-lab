from __future__ import annotations

from pathlib import Path

import pandas as pd

from perishable_lab.evaluation import (
    build_parameter_manifest,
    build_validation_gate,
    check_simulation_invariants,
    summarise_sensitivity,
)
from perishable_lab.inventory.policies import QuantileBaseStockPolicy
from perishable_lab.inventory.simulator import simulate_series


def _golden_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=4),
            "demand": [0, 2, 1, 0],
            "q50": [3.0] * 4,
            "service_q90": [3.0] * 4,
            "shelf_life_days": [2] * 4,
            "lead_time_days": [1] * 4,
            "unit_cost": [1.0] * 4,
            "unit_margin": [1.0] * 4,
            "waste_cost": [0.0] * 4,
            "shrinkage_rate": [0.0] * 4,
            "record_error_std": [0.0] * 4,
        }
    )


def test_golden_simulator_event_log_matches_fixture() -> None:
    result = simulate_series(
        _golden_frame(),
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        seed=7,
    )
    columns = [
        "date",
        "arrival",
        "opening_inventory",
        "fulfilled",
        "lost_sales",
        "expired_units",
        "shrinkage_units",
        "ending_inventory",
        "order_quantity",
        "supplier_filled_quantity",
        "pipeline_inventory",
    ]
    expected = pd.read_csv(Path("tests/fixtures/golden_simulation_expected.csv"), parse_dates=["date"])

    pd.testing.assert_frame_equal(result[columns].reset_index(drop=True), expected)


def test_simulator_invariant_gate_passes_for_golden_scenario() -> None:
    result = simulate_series(
        _golden_frame(),
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        seed=7,
    )
    issues = check_simulation_invariants(result)
    gate = build_validation_gate(
        issues,
        conceptual_validity="partially_validated",
        predictive_validity="not_validated",
    )

    assert issues.empty
    assert gate["software_verification"] == "pass"
    assert not gate["ready_for_policy_claims"]


def test_invariant_checker_detects_broken_mass_balance() -> None:
    result = simulate_series(
        _golden_frame(),
        QuantileBaseStockPolicy(),
        service_forecast_column="service_q90",
        seed=7,
    )
    result.loc[1, "ending_inventory"] = 99

    issues = check_simulation_invariants(result)

    assert "stock_conservation" in set(issues["rule_id"])


def test_parameter_manifest_checksum_is_deterministic() -> None:
    parameters = {"lead_time_days": 1, "shrinkage_rate": 0.01}

    first = build_parameter_manifest(parameters)
    second = build_parameter_manifest(dict(reversed(parameters.items())))

    assert first["checksum"] == second["checksum"]


def test_sensitivity_summary_reports_uncertainty_intervals() -> None:
    runs = pd.DataFrame(
        {
            "shrinkage_rate": [0.0, 0.0, 0.1, 0.1],
            "fill_rate": [0.9, 0.8, 0.7, 0.6],
            "waste_rate": [0.1, 0.2, 0.3, 0.4],
        }
    )

    summary = summarise_sensitivity(
        runs,
        parameter_columns=("shrinkage_rate",),
        kpi_columns=("fill_rate", "waste_rate"),
    )

    assert {"fill_rate_p05", "fill_rate_median", "fill_rate_p95"}.issubset(summary.columns)
