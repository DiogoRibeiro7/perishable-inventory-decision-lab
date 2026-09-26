"""Operational file failures retain their paths and original causes."""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import pytest
from dataexcept import DataLoadingError, FileWriteError, SchemaMismatchError

from case_study.evaluator import evaluate_outputs
from perishable_lab.config import load_config
from perishable_lab.data.adapters import LocalFileRetailAdapter
from perishable_lab.forecasting.quantile import QuantileForecaster
from perishable_lab.io import read_csv, write_csv
from perishable_lab.performance import write_benchmark_report
from perishable_lab.publication import LocalRecommendationStore


def test_missing_table_preserves_source_and_cause(tmp_path: Path) -> None:
    path = tmp_path / "sales.csv"

    with pytest.raises(DataLoadingError) as caught:
        LocalFileRetailAdapter(tmp_path).read_table("sales")

    assert caught.value.source == str(path)
    assert isinstance(caught.value.original, FileNotFoundError)
    assert caught.value.__cause__ is caught.value.original


def test_malformed_csv_preserves_parser_error(tmp_path: Path) -> None:
    path = tmp_path / "sales.csv"
    path.write_text('value\n"unclosed\n', encoding="utf-8")

    with pytest.raises(DataLoadingError) as caught:
        read_csv(path)

    assert caught.value.source == str(path)
    assert isinstance(caught.value.original, pd.errors.ParserError)


def test_config_distinguishes_parse_failure_from_schema_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("simulation: [unterminated\n", encoding="utf-8")

    with pytest.raises(DataLoadingError) as caught:
        load_config(path)
    assert caught.value.source == str(path)
    assert caught.value.__cause__ is caught.value.original

    path.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(SchemaMismatchError) as schema:
        load_config(path)
    assert schema.value.expected == "YAML mapping"
    assert schema.value.found == "list"


def test_corrupt_model_preserves_unpickling_error(tmp_path: Path) -> None:
    path = tmp_path / "model.pkl"
    path.write_bytes(b"not a pickle")

    with pytest.raises(DataLoadingError) as caught:
        QuantileForecaster.load(path)

    assert caught.value.source == str(path)
    assert isinstance(caught.value.original, pickle.UnpicklingError)


def test_invalid_model_state_keeps_domain_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="fitted"):
        QuantileForecaster().save(tmp_path / "model.pkl")


def test_csv_write_error_preserves_destination_and_cause(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "sales.csv"

    with pytest.raises(FileWriteError) as caught:
        write_csv(pd.DataFrame({"value": [1]}), path)

    assert caught.value.path == str(path)
    assert isinstance(caught.value.original, OSError)
    assert caught.value.__cause__ is caught.value.original


def test_report_and_publication_directory_failures_are_typed(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.write_text("file", encoding="utf-8")

    with pytest.raises(FileWriteError) as report:
        write_benchmark_report({"score": 1.0}, occupied)
    assert report.value.path == str(occupied)

    with pytest.raises(FileWriteError) as publication:
        LocalRecommendationStore(occupied)
    assert publication.value.path == str(occupied / "batches")


def test_case_study_evaluator_identifies_missing_submission(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.csv"
    with pytest.raises(DataLoadingError) as caught:
        evaluate_outputs(tmp_path, tmp_path)
    assert caught.value.source == str(path)
    assert isinstance(caught.value.original, FileNotFoundError)
