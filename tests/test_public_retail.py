from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from perishable_lab.cli import app
from perishable_lab.data.public_retail import (
    M5AdapterConfig,
    check_date_completeness,
    known_m5_leakage_fields,
    load_m5_canonical,
    public_dataset_candidates,
    run_public_retail_benchmark,
    sha256_file,
    validate_m5_files,
)


def _write_m5_fixture(raw_dir: Path, *, days: int = 110) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    calendar = pd.DataFrame(
        {
            "d": [f"d_{day}" for day in range(1, days + 1)],
            "date": pd.date_range("2011-01-29", periods=days, freq="D").date.astype(str),
            "wm_yr_wk": [11101 + (day - 1) // 7 for day in range(1, days + 1)],
            "event_name_1": [None if day % 11 else "event" for day in range(1, days + 1)],
            "event_name_2": [None] * days,
            "snap_CA": [day % 3 == 0 for day in range(1, days + 1)],
            "snap_TX": [False] * days,
            "snap_WI": [False] * days,
        }
    )
    sales_rows = []
    for store_id in ("CA_1", "TX_1"):
        for item_index, item_id in enumerate(("FOODS_1_001", "HOBBIES_1_001")):
            row = {
                "id": f"{item_id}_{store_id}_validation",
                "item_id": item_id,
                "dept_id": item_id.rsplit("_", maxsplit=1)[0],
                "cat_id": item_id.split("_", maxsplit=1)[0],
                "store_id": store_id,
                "state_id": store_id.split("_", maxsplit=1)[0],
            }
            for day in range(1, days + 1):
                row[f"d_{day}"] = max(0, item_index + (day % 7) + (1 if store_id == "CA_1" else 0))
            sales_rows.append(row)
    prices = []
    for store_id in ("CA_1", "TX_1"):
        for item_id in ("FOODS_1_001", "HOBBIES_1_001"):
            for week in sorted(calendar["wm_yr_wk"].unique()):
                prices.append(
                    {
                        "store_id": store_id,
                        "item_id": item_id,
                        "wm_yr_wk": week,
                        "sell_price": 2.0 if item_id.startswith("FOODS") else 4.0,
                    }
                )
    calendar.to_csv(raw_dir / "calendar.csv", index=False)
    pd.DataFrame(sales_rows).to_csv(raw_dir / "sales_train_validation.csv", index=False)
    pd.DataFrame(prices).to_csv(raw_dir / "sell_prices.csv", index=False)


def test_dataset_candidates_select_m5_for_methodological_fit() -> None:
    candidates = public_dataset_candidates()

    selected = [candidate for candidate in candidates if candidate.selected]
    assert [candidate.name for candidate in selected] == ["M5 Forecasting - Accuracy"]
    assert "on-hand inventory" in selected[0].missing_operational_fields


def test_validate_files_checks_missing_and_checksum(tmp_path: Path) -> None:
    _write_m5_fixture(tmp_path, days=35)
    checksums = validate_m5_files(tmp_path)

    assert checksums["calendar.csv"] == sha256_file(tmp_path / "calendar.csv")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        validate_m5_files(tmp_path, {"calendar.csv": "bad"})
    with pytest.raises(FileNotFoundError, match="Missing M5 files"):
        validate_m5_files(tmp_path / "missing")


def test_adapter_converts_schema_and_is_deterministic(tmp_path: Path) -> None:
    _write_m5_fixture(tmp_path, days=40)

    first = load_m5_canonical(M5AdapterConfig(tmp_path, max_series=3, seed=5))
    second = load_m5_canonical(M5AdapterConfig(tmp_path, max_series=3, seed=5))

    pd.testing.assert_frame_equal(first, second)
    assert {"date", "store_id", "product_id", "demand", "price", "promotion"}.issubset(first.columns)
    assert first["simulated_inventory_fields"].all()
    assert first[["date", "store_id", "product_id"]].duplicated().sum() == 0


def test_date_completeness_and_leakage_detection(tmp_path: Path) -> None:
    _write_m5_fixture(tmp_path, days=40)
    (tmp_path / "sample_submission.csv").write_text("id,F1\nx,1\n", encoding="utf-8")
    frame = load_m5_canonical(M5AdapterConfig(tmp_path, max_series=2, seed=8))
    completeness = check_date_completeness(frame)

    assert completeness["complete"].all()
    assert "sample_submission.csv" in known_m5_leakage_fields(tmp_path)


def test_public_benchmark_writes_reproducible_outputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    _write_m5_fixture(raw_dir, days=115)

    outputs = run_public_retail_benchmark(raw_dir, output_dir)
    metrics = pd.read_csv(outputs["forecast_metrics"])

    assert Path(outputs["manifest"]).exists()
    assert {"seasonal_naive", "sba_intermittent", "quantile_boosting"}.issubset(set(metrics["model"]))
    assert (output_dir / "synthetic_comparison.md").exists()


def test_public_benchmark_cli_handles_user_provided_files(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "cli-out"
    _write_m5_fixture(raw_dir, days=115)

    result = CliRunner().invoke(
        app,
        [
            "public-retail-benchmark",
            str(raw_dir),
            "--output-dir",
            str(output_dir),
            "--max-series",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "forecast_metrics.csv").exists()
