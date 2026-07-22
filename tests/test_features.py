from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.features import build_features, feature_columns


def test_features_are_lagged_and_model_ready() -> None:
    raw = generate_daily_demand(SyntheticDataSpec(days=80, stores=1, products=2))
    featured = build_features(raw)
    columns = feature_columns(featured)

    assert not featured.empty
    assert "demand_lag_1" in columns
    assert "demand" not in columns
    assert featured[columns].select_dtypes(exclude="number").empty
