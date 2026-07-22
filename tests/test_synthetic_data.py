from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.data.validation import validate_daily_demand


def test_synthetic_data_is_reproducible_and_valid() -> None:
    spec = SyntheticDataSpec(days=80, stores=2, products=3, seed=7)
    first = generate_daily_demand(spec)
    second = generate_daily_demand(spec)

    assert first.equals(second)
    assert len(first) == 80 * 2 * 3
    assert validate_daily_demand(first).is_valid
