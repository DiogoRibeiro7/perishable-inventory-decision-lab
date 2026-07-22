from __future__ import annotations

import pandas as pd

from perishable_lab.forecasting import (
    HierarchicalFallbackRouter,
    HierarchyConfig,
    build_cold_start_evaluation_report,
    build_hierarchical_features,
    empirical_bayes_shrinkage,
    reconcile_bottom_up,
)


def _history() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    return pd.DataFrame(
        {
            "date": list(dates) + list(dates),
            "store_id": ["S001"] * 40 + ["S002"] * 40,
            "product_id": ["P001"] * 40 + ["P002"] * 40,
            "category_id": ["C001"] * 80,
            "demand": list(range(1, 41)) + [3] * 40,
        }
    )


def test_unseen_category_falls_back_safely_to_global_history() -> None:
    history = _history()
    scoring = pd.DataFrame(
        {
            "date": ["2026-02-15"],
            "store_id": ["S009"],
            "product_id": ["P999"],
            "category_id": ["C999"],
        }
    )
    router = HierarchicalFallbackRouter(config=HierarchyConfig(min_parent_history=10))

    predictions, explanations = router.predict(scoring, history)

    assert predictions[["q05", "q50", "q95"]].notna().all(axis=None)
    assert (predictions[["q05", "q50", "q95"]] >= 0).all(axis=None)
    assert predictions.loc[0, "q05"] <= predictions.loc[0, "q50"] <= predictions.loc[0, "q95"]
    assert explanations.loc[0, "selected_source"] == "retailer"
    assert explanations.loc[0, "cold_start_state"] == "unseen_product"


def test_fallback_uses_no_future_history() -> None:
    history = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-02-01"],
            "store_id": ["S001", "S001", "S001"],
            "product_id": ["P001", "P001", "P001"],
            "category_id": ["C001", "C001", "C001"],
            "demand": [4, 6, 1000],
        }
    )
    scoring = pd.DataFrame(
        {
            "date": ["2026-01-03"],
            "store_id": ["S001"],
            "product_id": ["P001"],
            "category_id": ["C001"],
        }
    )
    router = HierarchicalFallbackRouter(
        config=HierarchyConfig(min_store_product_history=2, min_parent_history=2)
    )

    predictions, _ = router.predict(scoring, history)

    assert predictions.loc[0, "q50"] == 5.0


def test_hierarchy_join_is_as_of_correct() -> None:
    frame = pd.DataFrame({"date": ["2026-01-15"], "product_id": ["P001"], "store_id": ["S001"]})
    hierarchy = pd.DataFrame(
        [
            {
                "product_id": "P001",
                "category_id": "old",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "known_at": "2026-01-01T00:00:00Z",
            },
            {
                "product_id": "P001",
                "category_id": "new",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "known_at": "2026-02-01T00:00:00Z",
            },
        ]
    )

    historical = build_hierarchical_features(frame, hierarchy, known_at="2026-01-20T00:00:00Z")
    restated = build_hierarchical_features(frame, hierarchy, known_at="2026-02-02T00:00:00Z")

    assert historical.loc[0, "category_id"] == "old"
    assert restated.loc[0, "category_id"] == "new"


def test_reconciled_forecasts_obey_parent_sums() -> None:
    child = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01"],
            "category_id": ["C001", "C001"],
            "q50": [4.0, 6.0],
            "q95": [7.0, 9.0],
        }
    )

    parent = reconcile_bottom_up(
        child,
        group_columns=("date", "category_id"),
        quantile_columns=("q50", "q95"),
    )

    assert parent.loc[0, "q50"] == 10.0
    assert parent.loc[0, "q95"] == 16.0


def test_empirical_bayes_shrinkage_moves_toward_parent_for_sparse_series() -> None:
    sparse = empirical_bayes_shrinkage(20.0, 10.0, 1, prior_strength=9.0)
    mature = empirical_bayes_shrinkage(20.0, 10.0, 90, prior_strength=10.0)

    assert sparse == 11.0
    assert mature == 19.0


def test_cold_start_report_groups_metrics_by_state() -> None:
    predictions = pd.DataFrame(
        {
            "cold_start_state": ["unseen_product", "mature"],
            "demand": [5.0, 10.0],
            "q05": [2.0, 8.0],
            "q50": [6.0, 9.0],
            "q95": [8.0, 12.0],
        }
    )

    report = build_cold_start_evaluation_report(predictions)

    assert set(report["cold_start_state"]) == {"mature", "unseen_product"}
    assert {"bias", "mae", "coverage", "mean_width"}.issubset(report.columns)
