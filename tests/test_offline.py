from __future__ import annotations

import pandas as pd

from perishable_lab.offline import (
    counterfactual_report,
    deterministic_replay,
    doubly_robust_value,
    inverse_propensity_weighted_value,
    sensitivity_bounds,
    support_diagnostics,
)


def _logged() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "logged_action": [1, 1, 2, 2],
            "candidate_action": [1, 1, 2, 2],
            "propensity": [0.5, 0.5, 0.5, 0.5],
            "reward": [10.0, 10.0, 20.0, 20.0],
            "q_logged": [10.0, 10.0, 20.0, 20.0],
            "q_candidate": [10.0, 10.0, 20.0, 20.0],
        }
    )


def test_ipw_recovers_known_policy_value_with_good_overlap() -> None:
    result = inverse_propensity_weighted_value(
        _logged(),
        outcome_column="reward",
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
        minimum_effective_sample_size=2,
    )

    assert result.status == "estimated"
    assert result.value == 30.0


def test_weak_overlap_refuses_confident_estimate() -> None:
    logged = _logged()
    logged["candidate_action"] = 9

    result = inverse_propensity_weighted_value(
        logged,
        outcome_column="reward",
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
    )

    assert result.status == "not_identifiable"
    assert result.value is None


def test_extreme_weights_fail_support_diagnostics() -> None:
    logged = _logged()
    logged.loc[0, "propensity"] = 0.001

    diagnostics = support_diagnostics(
        logged,
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
        minimum_effective_sample_size=10,
    )

    assert not diagnostics.adequate_overlap
    assert diagnostics.failure_reason == "weak_overlap_or_extreme_weights"


def test_doubly_robust_estimator_is_reproducible() -> None:
    first = doubly_robust_value(
        _logged(),
        outcome_column="reward",
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
        q_logged_column="q_logged",
        q_candidate_column="q_candidate",
        minimum_effective_sample_size=2,
    )
    second = doubly_robust_value(
        _logged(),
        outcome_column="reward",
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
        q_logged_column="q_logged",
        q_candidate_column="q_candidate",
        minimum_effective_sample_size=2,
    )

    assert first == second


def test_hidden_confounding_returns_bounds() -> None:
    bounds = sensitivity_bounds(
        10.0,
        hidden_lost_demand_delta=3.0,
        hidden_inventory_delta=2.0,
    )

    assert bounds["lower_bound"] == 5.0
    assert bounds["upper_bound"] == 15.0


def test_counterfactual_report_labels_identification_failure() -> None:
    logged = _logged()
    logged["candidate_action"] = 9
    result = inverse_propensity_weighted_value(
        logged,
        outcome_column="reward",
        action_column="logged_action",
        candidate_action_column="candidate_action",
        propensity_column="propensity",
    )

    report = counterfactual_report(result)

    assert report["status"] == "not_identifiable"
    assert report["outcome_label"] == "not_identifiable"


def test_deterministic_replay_labels_reconstructable_rows() -> None:
    replayed = deterministic_replay(_logged(), invariant_columns=("reward",))

    assert set(replayed["outcome_label"]) == {"observed"}
