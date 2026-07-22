"""Evaluator-only checks for the take-home exercise."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class EvaluationResult:
    """Score and checks returned by the evaluator."""

    score: float
    checks: dict[str, bool]
    metrics: dict[str, float]


def check_no_truth_leakage(recommendations: pd.DataFrame) -> bool:
    """Return false when evaluator-only columns appear in candidate outputs."""
    forbidden = {"true_demand", "future_demand", "oracle_quantity"}
    return forbidden.isdisjoint(recommendations.columns)


def check_duplicate_keys(frame: pd.DataFrame) -> bool:
    """Return true when recommendation keys are unique."""
    keys = ["date", "store_id", "product_id"]
    return not frame.duplicated(keys).any()


def check_recommendation_constraints(recommendations: pd.DataFrame, products: pd.DataFrame) -> bool:
    """Validate non-negative orders, capacity, minimum order, and pack-size constraints."""
    joined = recommendations.merge(products, on="product_id", how="left", validate="many_to_one")
    if joined[["case_pack", "minimum_order_quantity", "storage_capacity_units"]].isna().any().any():
        return False
    quantity = joined["recommended_order_units"].astype(int)
    case_pack = joined["case_pack"].astype(int)
    minimum = joined["minimum_order_quantity"].astype(int)
    capacity = joined["storage_capacity_units"].astype(int)
    non_negative = (quantity >= 0).all()
    pack_aligned = ((quantity == 0) | (quantity % case_pack == 0)).all()
    minimum_ok = ((quantity == 0) | (quantity >= minimum)).all()
    capacity_ok = (quantity <= capacity).all()
    return bool(non_negative and pack_aligned and minimum_ok and capacity_ok)


def check_stock_conservation(metrics: dict[str, float], tolerance: float = 1e-9) -> bool:
    """Check that fulfilled and lost demand sum to true demand in aggregate."""
    demand = metrics.get("true_demand_units", 0.0)
    fulfilled = metrics.get("fulfilled_units", 0.0)
    lost = metrics.get("lost_sales_units", 0.0)
    return abs(demand - fulfilled - lost) <= tolerance


def evaluate_outputs(data_dir: Path, submission_dir: Path) -> EvaluationResult:
    """Evaluate reference-style outputs against hidden truth."""
    recommendations = pd.read_csv(submission_dir / "recommendations.csv")
    metrics = pd.read_json(submission_dir / "metrics.json", typ="series").to_dict()
    products = pd.read_csv(data_dir / "products.csv")

    checks = {
        "no_truth_leakage": check_no_truth_leakage(recommendations),
        "unique_recommendation_keys": check_duplicate_keys(recommendations),
        "recommendation_constraints": check_recommendation_constraints(recommendations, products),
        "stock_conservation": check_stock_conservation({key: float(value) for key, value in metrics.items()}),
    }
    score = 100.0 * sum(checks.values()) / len(checks)
    return EvaluationResult(
        score=score,
        checks=checks,
        metrics={key: float(value) for key, value in metrics.items() if isinstance(value, int | float)},
    )
