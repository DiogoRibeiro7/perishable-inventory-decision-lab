"""Evaluation report helpers for forecast and policy backtests."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def paired_block_bootstrap_difference(
    frame: pd.DataFrame,
    *,
    baseline_column: str,
    candidate_column: str,
    block_size: int = 7,
    n_resamples: int = 500,
    seed: int = 42,
) -> dict[str, float]:
    """Estimate a confidence interval for paired candidate-minus-baseline means."""
    if block_size < 1 or n_resamples < 1:
        raise ValueError("Block size and resample count must be positive")
    missing = {baseline_column, candidate_column}.difference(frame.columns)
    if missing:
        raise ValueError(f"Bootstrap frame is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Bootstrap frame cannot be empty")

    differences = (
        frame[candidate_column].to_numpy(dtype=np.float64)
        - frame[baseline_column].to_numpy(dtype=np.float64)
    )
    blocks = [
        differences[start : start + block_size]
        for start in range(0, len(differences), block_size)
        if len(differences[start : start + block_size]) > 0
    ]
    rng = np.random.default_rng(seed)
    sampled_means = np.empty(n_resamples, dtype=np.float64)
    for sample_index in range(n_resamples):
        selected = rng.integers(0, len(blocks), size=len(blocks))
        sampled = np.concatenate([blocks[index] for index in selected])
        sampled_means[sample_index] = float(np.mean(sampled))

    return {
        "mean_difference": float(np.mean(differences)),
        "lower_95": float(np.quantile(sampled_means, 0.025)),
        "upper_95": float(np.quantile(sampled_means, 0.975)),
    }


def build_evaluation_report(
    *,
    forecast_metrics: dict[str, Any],
    policy_metrics: pd.DataFrame,
    monitoring_report: dict[str, Any],
    baseline_policy: str = "median_baseline",
) -> dict[str, Any]:
    """Create a serialisable report that separates forecast and policy quality."""
    if policy_metrics.empty:
        raise ValueError("Policy metrics cannot be empty")
    required = {"policy", "total_cost", "fill_rate", "waste_rate", "lost_sales_rate"}
    missing = required.difference(policy_metrics.columns)
    if missing:
        raise ValueError(f"Policy metrics are missing columns: {sorted(missing)}")

    ranked = policy_metrics.sort_values(["total_cost", "lost_sales_rate"]).reset_index(drop=True)
    best = ranked.iloc[0].to_dict()
    baseline_rows = policy_metrics.loc[policy_metrics["policy"] == baseline_policy]
    baseline = baseline_rows.iloc[0].to_dict() if not baseline_rows.empty else best
    cost_delta = float(best["total_cost"]) - float(baseline["total_cost"])
    fill_rate_delta = float(best["fill_rate"]) - float(baseline["fill_rate"])

    return {
        "forecast": {
            "rows": int(forecast_metrics["rows"]),
            "empirical_coverage": float(forecast_metrics["empirical_coverage"]),
            "approximate_crps": float(forecast_metrics["approximate_crps"]),
        },
        "policy": {
            "baseline_policy": baseline_policy,
            "selected_policy": str(best["policy"]),
            "total_cost_delta_vs_baseline": cost_delta,
            "fill_rate_delta_vs_baseline": fill_rate_delta,
            "ranked": ranked.to_dict(orient="records"),
        },
        "monitoring": {
            "status": monitoring_report["status"],
            "alerts": monitoring_report["alerts"],
        },
    }


__all__ = ["build_evaluation_report", "paired_block_bootstrap_difference"]
