from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.features import TARGET_COLUMN, build_features, feature_columns
from perishable_lab.forecasting.baselines import (
    SeasonalNaiveQuantileForecaster,
    sba_intermittent_forecast,
)
from perishable_lab.forecasting.horizon import cumulative_quantile_forecast, lead_time_horizons
from perishable_lab.forecasting.quantile import QuantileForecaster


def test_cumulative_forecast_is_finite_non_negative_and_monotone() -> None:
    predictions = pd.DataFrame({"q10": [2.0, 0.0], "q50": [4.0, 1.0], "q90": [8.0, 3.0]})
    horizons = lead_time_horizons(pd.DataFrame({"lead_time_days": [1, 2]}), review_period_days=1)

    cumulative = cumulative_quantile_forecast(predictions, (0.1, 0.5, 0.9), horizons)

    assert cumulative.columns.tolist() == ["lead_time_q10", "lead_time_q50", "lead_time_q90"]
    assert (cumulative >= 0.0).all().all()
    assert (cumulative["lead_time_q10"] <= cumulative["lead_time_q50"]).all()
    assert (cumulative["lead_time_q50"] <= cumulative["lead_time_q90"]).all()


def test_seasonal_fallback_handles_cold_start_products() -> None:
    history = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=14, freq="D"),
            "store_id": ["S001"] * 14,
            "product_id": ["P001"] * 14,
            "demand": [1, 0, 3, 2, 4, 0, 2, 2, 1, 4, 3, 5, 1, 3],
        }
    )
    scoring = pd.DataFrame(
        {
            "date": ["2025-01-15"],
            "store_id": ["S999"],
            "product_id": ["new-product"],
        }
    )

    fallback = SeasonalNaiveQuantileForecaster(quantiles=(0.1, 0.5, 0.9)).fit(history)
    predictions = fallback.predict(scoring)

    assert predictions.loc[0, "q10"] >= 0.0
    assert predictions.loc[0, "q10"] <= predictions.loc[0, "q50"] <= predictions.loc[0, "q90"]


def test_sba_intermittent_forecast_is_non_negative() -> None:
    assert sba_intermittent_forecast(pd.Series([0, 0, 0])) == 0.0
    assert sba_intermittent_forecast(pd.Series([0, 4, 0, 0, 6, 0])) > 0.0


def test_quantile_forecaster_serialization_round_trip(tmp_path: Path) -> None:
    raw = generate_daily_demand(SyntheticDataSpec(days=90, stores=1, products=2, seed=13))
    featured = build_features(raw)
    columns = feature_columns(featured)
    train = featured.iloc[:80]
    score = featured.iloc[80:]
    model = QuantileForecaster(
        quantiles=(0.1, 0.5, 0.9),
        max_iter=20,
        min_samples_leaf=5,
        random_state=13,
    ).fit(train[columns], train[TARGET_COLUMN])

    path = tmp_path / "forecaster.pkl"
    model.save(path)
    loaded = QuantileForecaster.load(path)

    pd.testing.assert_frame_equal(model.predict(score[columns]), loaded.predict(score[columns]))


def test_quantile_forecaster_respects_censored_row_weight_modes() -> None:
    features = pd.DataFrame({"signal": [0.0] * 10 + [1.0] * 10})
    target = pd.Series([1.0] * 10 + [100.0] * 10)
    scoring = pd.DataFrame({"signal": [1.0]})
    settings = {
        "quantiles": (0.5,),
        "max_iter": 80,
        "min_samples_leaf": 1,
        "random_state": 7,
    }

    included = QuantileForecaster(**settings).fit(features, target).predict(scoring).loc[0, "q50"]
    excluded_weights = pd.Series([1.0] * 10 + [0.0] * 10)
    excluded = (
        QuantileForecaster(**settings)
        .fit(features, target, sample_weight=excluded_weights)
        .predict(scoring)
        .loc[0, "q50"]
    )
    downweighted = (
        QuantileForecaster(**settings)
        .fit(features, target, sample_weight=np.where(excluded_weights == 0.0, 0.05, 1.0))
        .predict(scoring)
        .loc[0, "q50"]
    )

    assert included > 90.0
    assert excluded < 10.0
    assert downweighted < included


def test_quantile_forecaster_rejects_invalid_sample_weights() -> None:
    features = pd.DataFrame({"signal": [0.0, 1.0]})
    target = pd.Series([1.0, 2.0])
    model = QuantileForecaster(quantiles=(0.5,), max_iter=5, min_samples_leaf=1)

    with pytest.raises(ValueError, match="cannot be negative"):
        model.fit(features, target, sample_weight=pd.Series([1.0, -1.0]))
