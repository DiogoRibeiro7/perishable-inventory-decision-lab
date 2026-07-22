from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from perishable_lab.cli import app
from perishable_lab.failures import (
    build_episode_records,
    diagnose_failures,
    paired_error_summary,
    rank_failure_cohorts,
    records_to_frame,
    write_failure_analysis,
    write_regression_fixture,
)


def _failure_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "store_id": "S1",
                "product_id": "P1",
                "demand": 18,
                "q50": 10,
                "q90": 12,
                "lost_sales": 7,
                "waste_units": 0,
                "unit_margin": 4.0,
                "unit_cost": 1.0,
                "waste_cost": 0.2,
                "missing_source_count": 1,
                "mapping_confidence": 0.70,
                "stockout_observed": True,
            },
            {
                "date": "2026-01-02",
                "store_id": "S1",
                "product_id": "P1",
                "demand": 9,
                "q50": 12,
                "q90": 20,
                "lost_sales": 0,
                "waste_units": 1,
                "unit_margin": 4.0,
                "unit_cost": 1.0,
                "waste_cost": 0.2,
                "supplier_fill_rate": 0.60,
            },
            {
                "date": "2026-01-03",
                "store_id": "S2",
                "product_id": "P2",
                "demand": 10,
                "q50": 30,
                "q90": 35,
                "lost_sales": 0,
                "waste_units": 0,
                "unit_margin": 2.0,
                "unit_cost": 1.0,
                "waste_cost": 0.1,
            },
            {
                "date": "2026-01-04",
                "store_id": "S2",
                "product_id": "P3",
                "demand": 12,
                "q50": 11,
                "q90": 20,
                "lost_sales": 8,
                "waste_units": 0,
                "unit_margin": 5.0,
                "unit_cost": 1.0,
                "waste_cost": 0.1,
                "order_constraint_gap_units": 8,
            },
        ]
    )


def test_multi_cause_rows_and_unknown_cause_are_recorded() -> None:
    records = diagnose_failures(_failure_frame())

    first = records[0]
    assert {signal.cause for signal in first.causes}.issuperset(
        {"missing_or_late_data", "product_mapping_error", "stockout_censored_target", "tail_undercoverage"}
    )
    assert records[2].primary_cause == "unknown"


def test_episode_ranking_is_deterministic_and_impact_sorted() -> None:
    records = diagnose_failures(_failure_frame())
    episodes = build_episode_records(records)
    ranked = rank_failure_cohorts(records)
    repeated = build_episode_records(records)

    assert list(ranked["impact_score"]) == sorted(ranked["impact_score"], reverse=True)
    assert [episode.primary_cause for episode in episodes] == [episode.primary_cause for episode in repeated]
    assert records_to_frame(records).shape[0] == 4


def test_real_time_mode_does_not_use_outcome_only_signals() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "store_id": "S1",
                "product_id": "P1",
                "demand": 40,
                "q50": 5,
                "q90": 10,
                "lost_sales": 20,
                "stockout_observed": True,
            }
        ]
    )

    real_time = diagnose_failures(frame, mode="real_time")[0]
    post_outcome = diagnose_failures(frame, mode="post_outcome")[0]

    assert real_time.primary_cause == "unknown"
    assert {signal.cause for signal in post_outcome.causes}.issuperset(
        {"tail_undercoverage", "stockout_censored_target"}
    )


def test_paired_analysis_separates_forecast_and_decision_errors() -> None:
    summary = paired_error_summary(diagnose_failures(_failure_frame()))

    assert summary["statistically_poor_order_acceptable"] == 1
    assert summary["small_forecast_error_high_decision_cost"] == 1


def test_write_outputs_and_regression_fixture(tmp_path: Path) -> None:
    frame = _failure_frame()
    outputs = write_failure_analysis(frame, tmp_path)
    records = diagnose_failures(frame)
    fixture = write_regression_fixture(
        frame,
        records,
        tmp_path / "fixtures" / "confirmed.json",
        record_id=records[0].record_id,
    )

    assert Path(outputs["records"]).exists()
    assert Path(outputs["episodes"]).exists()
    assert Path(outputs["report"]).read_text(encoding="utf-8").startswith("# Failure Analysis Report")
    assert fixture.exists()


def test_diagnostic_cli_writes_report(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"
    _failure_frame().to_csv(input_path, index=False)

    result = CliRunner().invoke(
        app,
        ["diagnose-failures", str(input_path), "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0
    assert (output_dir / "failure_records.csv").exists()
