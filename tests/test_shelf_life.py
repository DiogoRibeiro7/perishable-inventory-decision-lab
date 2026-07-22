from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.shelf_life import (
    ConservativeShelfLifeFallback,
    EmpiricalShelfLifeModel,
    MasterDataShelfLifeModel,
    ShelfLifeError,
    compare_fixed_vs_stochastic_shelf_life,
    expand_batch_life_scenarios,
    prepare_shelf_life_observations,
)


def _observations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "batch_id": ["b1", "b2", "b3", "b4"],
            "product_id": ["P001", "P001", "P001", "P001"],
            "supplier_id": ["SUP1", "SUP1", "SUP1", "SUP1"],
            "receipt_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "expiry_date": ["2026-01-04", "2026-01-06", "2026-01-06", None],
            "observed_life_days": [3, 4, 3, 2],
            "right_censored": [False, False, False, True],
        }
    )


def test_censored_batches_are_retained_without_driving_empirical_distribution() -> None:
    fallback = ConservativeShelfLifeFallback(default_life_days=1)
    model = EmpiricalShelfLifeModel.fit(_observations(), fallback=fallback, min_samples=2)

    distribution = model.distribution_for("P001", "SUP1", season="winter")

    assert distribution.sample_size == 3
    assert distribution.censored_observations == 1
    assert distribution.support_days == (3, 4)


def test_impossible_negative_life_is_rejected() -> None:
    observations = _observations()
    observations.loc[0, "observed_life_days"] = -1
    observations = observations.drop(columns=["expiry_date"])

    with pytest.raises(ShelfLifeError, match="cannot be negative"):
        prepare_shelf_life_observations(observations)


def test_delivery_after_expiry_is_rejected() -> None:
    observations = _observations()
    observations.loc[0, "expiry_date"] = "2025-12-31"

    with pytest.raises(ShelfLifeError, match="after expiry"):
        prepare_shelf_life_observations(observations)


def test_sparse_groups_use_declared_conservative_fallback() -> None:
    master = MasterDataShelfLifeModel(pd.DataFrame({"product_id": ["P001"], "shelf_life_days": [5]}))
    model = EmpiricalShelfLifeModel.fit(_observations().iloc[[0]], fallback=master, min_samples=2)

    distribution = model.distribution_for("P001", "SUP1")

    assert distribution.source == "master_data"
    assert distribution.support_days == (5,)


def test_sampling_is_deterministic_by_seed() -> None:
    fallback = ConservativeShelfLifeFallback(default_life_days=1)
    model = EmpiricalShelfLifeModel.fit(_observations(), fallback=fallback, min_samples=2)
    distribution = model.distribution_for("P001", "SUP1")

    first = distribution.sample(5, seed=7)
    second = distribution.sample(5, seed=7)

    assert first.tolist() == second.tolist()


def test_batch_scenarios_preserve_quantity_with_multiple_distributions() -> None:
    fallback = ConservativeShelfLifeFallback(default_life_days=2)
    model = EmpiricalShelfLifeModel.fit(_observations(), fallback=fallback, min_samples=2)
    batches = pd.DataFrame(
        {
            "batch_id": ["b1", "b2"],
            "product_id": ["P001", "P999"],
            "supplier_id": ["SUP1", "SUP9"],
            "quantity": [5, 7],
        }
    )

    scenarios = expand_batch_life_scenarios(batches, model, scenarios=3, seed=3)

    assert scenarios.groupby("scenario_id")["quantity"].sum().tolist() == [12, 12, 12]
    assert set(scenarios["distribution_source"]) == {
        "empirical_product_supplier_season",
        "conservative_fallback",
    }


def test_fixed_vs_stochastic_comparison_reports_expiry_risk() -> None:
    fallback = ConservativeShelfLifeFallback(default_life_days=1)
    model = EmpiricalShelfLifeModel.fit(_observations(), fallback=fallback, min_samples=2)
    frame = pd.DataFrame(
        {"product_id": ["P001"], "supplier_id": ["SUP1"], "shelf_life_days": [5]}
    )

    comparison = compare_fixed_vs_stochastic_shelf_life(frame, model, risk_horizon_days=3)

    assert comparison.loc[0, "fixed_expiry_risk"] == 0.0
    assert comparison.loc[0, "stochastic_expiry_risk"] > 0.0
