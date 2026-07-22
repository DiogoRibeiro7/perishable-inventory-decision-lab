"""Offline policy evaluation and counterfactual guardrails."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

OutcomeLabel = Literal["observed", "reconstructed", "simulated", "estimated", "not_identifiable"]


@dataclass(frozen=True)
class SupportDiagnostics:
    """Overlap and weight diagnostics for logged-policy evaluation."""

    rows: int
    matched_rows: int
    effective_sample_size: float
    max_weight: float
    min_propensity: float
    adequate_overlap: bool
    failure_reason: str | None = None


@dataclass(frozen=True)
class OfflineEvaluationResult:
    """Auditable offline policy evaluation result."""

    estimator: str
    value: float | None
    variance: float | None
    status: Literal["estimated", "not_identifiable", "bounds_only"]
    diagnostics: SupportDiagnostics
    outcome_label: OutcomeLabel
    assumptions: tuple[str, ...]


def assumption_checklist() -> tuple[str, ...]:
    """Return required assumptions for counterfactual policy-lift claims."""
    return (
        "logged actions have known or estimable propensities",
        "candidate actions overlap with historical actions",
        "outcomes are observed or reconstructed without policy-dependent censoring",
        "hidden inventory and lost demand sensitivity bounds are acceptable",
        "training, calibration, selection, and final evaluation periods are separated",
    )


def support_diagnostics(
    logged: pd.DataFrame,
    *,
    action_column: str,
    candidate_action_column: str,
    propensity_column: str,
    minimum_propensity: float = 0.05,
    minimum_effective_sample_size: float = 10.0,
) -> SupportDiagnostics:
    """Compute overlap diagnostics for a candidate policy against logged actions."""
    matched = logged[action_column] == logged[candidate_action_column]
    propensities = pd.to_numeric(logged.loc[matched, propensity_column], errors="coerce")
    if propensities.empty:
        return SupportDiagnostics(
            rows=int(logged.shape[0]),
            matched_rows=0,
            effective_sample_size=0.0,
            max_weight=float("inf"),
            min_propensity=0.0,
            adequate_overlap=False,
            failure_reason="no_action_overlap",
        )
    weights = 1.0 / propensities.clip(lower=1e-12)
    ess = float(weights.sum() ** 2 / np.square(weights).sum())
    min_propensity = float(propensities.min())
    max_weight = float(weights.max())
    adequate = min_propensity >= minimum_propensity and ess >= minimum_effective_sample_size
    reason = None
    if not adequate:
        reason = "weak_overlap_or_extreme_weights"
    return SupportDiagnostics(
        rows=int(logged.shape[0]),
        matched_rows=int(matched.sum()),
        effective_sample_size=ess,
        max_weight=max_weight,
        min_propensity=min_propensity,
        adequate_overlap=adequate,
        failure_reason=reason,
    )


def inverse_propensity_weighted_value(
    logged: pd.DataFrame,
    *,
    outcome_column: str,
    action_column: str,
    candidate_action_column: str,
    propensity_column: str,
    minimum_effective_sample_size: float = 10.0,
) -> OfflineEvaluationResult:
    """Estimate policy value with IPW only when overlap is adequate."""
    diagnostics = support_diagnostics(
        logged,
        action_column=action_column,
        candidate_action_column=candidate_action_column,
        propensity_column=propensity_column,
        minimum_effective_sample_size=minimum_effective_sample_size,
    )
    assumptions = assumption_checklist()
    if not diagnostics.adequate_overlap:
        return OfflineEvaluationResult(
            "ipw",
            None,
            None,
            "not_identifiable",
            diagnostics,
            "not_identifiable",
            assumptions,
        )
    matched = logged[action_column] == logged[candidate_action_column]
    outcomes = pd.to_numeric(logged.loc[matched, outcome_column], errors="coerce")
    propensities = pd.to_numeric(logged.loc[matched, propensity_column], errors="coerce")
    weighted = outcomes / propensities
    value = float(weighted.sum() / len(logged))
    variance = float(weighted.var(ddof=0) / max(len(logged), 1))
    return OfflineEvaluationResult("ipw", value, variance, "estimated", diagnostics, "estimated", assumptions)


def doubly_robust_value(
    logged: pd.DataFrame,
    *,
    outcome_column: str,
    action_column: str,
    candidate_action_column: str,
    propensity_column: str,
    q_logged_column: str,
    q_candidate_column: str,
    minimum_effective_sample_size: float = 10.0,
) -> OfflineEvaluationResult:
    """Estimate value with a doubly robust correction when assumptions pass diagnostics."""
    diagnostics = support_diagnostics(
        logged,
        action_column=action_column,
        candidate_action_column=candidate_action_column,
        propensity_column=propensity_column,
        minimum_effective_sample_size=minimum_effective_sample_size,
    )
    assumptions = assumption_checklist()
    if not diagnostics.adequate_overlap:
        return OfflineEvaluationResult("doubly_robust", None, None, "not_identifiable", diagnostics, "not_identifiable", assumptions)
    matched = logged[action_column] == logged[candidate_action_column]
    reward = pd.to_numeric(logged[outcome_column], errors="coerce")
    q_logged = pd.to_numeric(logged[q_logged_column], errors="coerce")
    q_candidate = pd.to_numeric(logged[q_candidate_column], errors="coerce")
    propensities = pd.to_numeric(logged[propensity_column], errors="coerce").clip(lower=1e-12)
    correction = matched.astype(float) * (reward - q_logged) / propensities
    estimates = q_candidate + correction
    return OfflineEvaluationResult(
        "doubly_robust",
        float(estimates.mean()),
        float(estimates.var(ddof=0) / max(len(estimates), 1)),
        "estimated",
        diagnostics,
        "estimated",
        assumptions,
    )


def deterministic_replay(frame: pd.DataFrame, *, invariant_columns: tuple[str, ...]) -> pd.DataFrame:
    """Label outcomes that are replayable without counterfactual assumptions."""
    replayed = frame.copy(deep=True)
    replayed["outcome_label"] = "observed"
    for column in invariant_columns:
        if column not in replayed.columns:
            replayed["outcome_label"] = "estimated"
    return replayed


def sensitivity_bounds(
    observed_value: float,
    *,
    hidden_lost_demand_delta: float,
    hidden_inventory_delta: float,
) -> dict[str, float | str]:
    """Return conservative value bounds under hidden demand and inventory uncertainty."""
    width = abs(hidden_lost_demand_delta) + abs(hidden_inventory_delta)
    return {
        "lower_bound": observed_value - width,
        "upper_bound": observed_value + width,
        "outcome_label": "estimated",
    }


def counterfactual_report(result: OfflineEvaluationResult) -> dict[str, object]:
    """Return a serialisable counterfactual report."""
    return {
        "estimator": result.estimator,
        "value": result.value,
        "variance": result.variance,
        "status": result.status,
        "outcome_label": result.outcome_label,
        "diagnostics": asdict(result.diagnostics),
        "assumptions": list(result.assumptions),
    }
