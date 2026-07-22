from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.demand_censoring import (
    ComparablePeriodImputer,
    ConservativeExcludeStrategy,
    DemandBoundsStrategy,
    DemandCensoringError,
    IterativeImputeRefitStrategy,
    build_censoring_diagnostic_report,
)


def _censoring_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-04",
                    "2026-01-05",
                ]
            ),
            "store_id": ["S001"] * 5,
            "product_id": ["P001"] * 5,
            "observed_sales": [4, 5, 2, 100, 6],
            "true_demand": [4, 5, 8, 100, 6],
            "observed_inventory": [10, 8, 0, 30, 9],
            "stockout_flag": [False, False, True, False, False],
            "promotion": [False, False, False, False, False],
        }
    )


def test_no_stockout_equivalence_preserves_observed_sales() -> None:
    frame = _censoring_frame().iloc[[0, 1, 4]].copy()

    result = ConservativeExcludeStrategy().adjust(frame)

    assert result.diagnostics.censored_rows == 0
    assert result.frame["latent_demand_estimate"].tolist() == [4.0, 5.0, 6.0]
    assert result.frame["latent_demand_training_weight"].tolist() == [1.0, 1.0, 1.0]


def test_complete_stockout_bounds_keep_point_estimate_conservative() -> None:
    result = DemandBoundsStrategy(min_history=1).adjust(_censoring_frame())
    censored = result.frame[result.frame["is_censored_demand"]].iloc[0]

    assert censored["latent_demand_lower"] == censored["observed_sales"]
    assert censored["latent_demand_estimate"] == censored["observed_sales"]
    assert censored["latent_demand_upper"] >= censored["latent_demand_lower"]
    assert censored["latent_demand_provenance"] == "historical_demand_bounds"


def test_impossible_inventory_records_are_rejected() -> None:
    frame = _censoring_frame()
    frame.loc[0, "observed_inventory"] = -1

    with pytest.raises(DemandCensoringError):
        ComparablePeriodImputer().adjust(frame)


def test_iterative_convergence_is_deterministic() -> None:
    frame = _censoring_frame()

    first = IterativeImputeRefitStrategy(min_history=1, max_iterations=5).adjust(frame)
    second = IterativeImputeRefitStrategy(min_history=1, max_iterations=5).adjust(frame)

    assert first.diagnostics == second.diagnostics
    pd.testing.assert_series_equal(
        first.frame["latent_demand_estimate"],
        second.frame["latent_demand_estimate"],
    )


def test_comparable_imputer_uses_no_future_information() -> None:
    frame = _censoring_frame()

    result = ComparablePeriodImputer(min_history=1).adjust(frame)
    censored = result.frame[result.frame["date"] == pd.Timestamp("2026-01-03")].iloc[0]

    assert censored["latent_demand_estimate"] == 4.5


def test_stockout_never_implies_latent_demand_below_observed_sales() -> None:
    result = ComparablePeriodImputer(min_history=1).adjust(_censoring_frame())

    assert (
        result.frame["latent_demand_estimate"] >= result.frame["observed_sales"]
    ).all()


def test_censoring_diagnostic_report_uses_ground_truth_when_available() -> None:
    result = ComparablePeriodImputer(min_history=1).adjust(_censoring_frame())

    report = build_censoring_diagnostic_report(result, true_demand_column="true_demand")

    assert {"bias", "mae", "interval_coverage"}.issubset(report.columns)
    assert report["censored_rows"].sum() >= 1
