from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from case_study.evaluator import (
    check_duplicate_keys,
    check_no_truth_leakage,
    check_recommendation_constraints,
    check_stock_conservation,
    evaluate_outputs,
)
from case_study.generator import CaseStudySpec, generate_case_study_data
from case_study.reference_solution import build_training_frame, run_reference_solution


def test_generator_writes_public_files_and_hidden_truth(tmp_path: Path) -> None:
    paths = generate_case_study_data(tmp_path, CaseStudySpec(days=60, seed=7))

    assert Path(paths["sales"]).exists()
    assert Path(paths["truth"]).parent.name == "evaluator_only"
    assert Path(paths["metadata"]).exists()

    sales = pd.read_csv(paths["sales"])
    assert sales.duplicated(["date", "store_id", "product_id"]).any()
    assert (sales["transaction_count"] < 0).any()


def test_reference_solution_filters_late_records_and_deduplicates(tmp_path: Path) -> None:
    generate_case_study_data(tmp_path, CaseStudySpec(days=60, seed=11))
    frame = build_training_frame(tmp_path)

    assert not frame.duplicated(["date", "store_id", "product_id"]).any()
    assert (frame["observed_inventory"] >= 0).all()
    assert frame["promotion_flag"].sum() >= 1

    late_promo = pd.read_csv(tmp_path / "promotions.csv").iloc[0]
    filtered_row = frame.loc[
        (frame["date"] == late_promo["date"])
        & (frame["store_id"] == late_promo["store_id"])
        & (frame["product_id"] == late_promo["product_id"])
    ].iloc[0]
    assert filtered_row["promotion_flag"] == 0


def test_reference_solution_outputs_pass_evaluator_checks(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    solution_dir = tmp_path / "solution"
    generate_case_study_data(data_dir, CaseStudySpec(days=70, seed=19))
    outputs = run_reference_solution(data_dir, solution_dir)

    recommendations = pd.read_csv(outputs["recommendations"])
    products = pd.read_csv(data_dir / "products.csv")
    metrics = json.loads(Path(outputs["metrics"]).read_text(encoding="utf-8"))
    result = evaluate_outputs(data_dir, solution_dir)

    assert check_no_truth_leakage(recommendations)
    assert check_duplicate_keys(recommendations)
    assert check_recommendation_constraints(recommendations, products)
    assert check_stock_conservation(metrics)
    assert result.score == 100.0
