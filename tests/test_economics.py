from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from perishable_lab.economics import (
    BusinessParameter,
    ParameterRegistry,
    classify_policy_stability,
    convert_currency,
    economic_terms_from_registry,
    sample_parameter_uncertainty,
    tornado_sensitivity,
)


def _parameter(name: str, value: float, *, lower: float | None = None, upper: float | None = None) -> BusinessParameter:
    return BusinessParameter(
        name=name,
        value=value,
        lower=value if lower is None else lower,
        upper=value if upper is None else upper,
        unit="EUR_per_unit" if "probability" not in name and "floor" not in name else "unit_probability",
        currency=None if "probability" in name or "floor" in name else "EUR",
        owner="finance",
        source="estimated",
        effective_from=date(2026, 1, 1),
    )


def _parameters() -> list[BusinessParameter]:
    return [
        _parameter("gross_margin", 2.0, lower=1.0, upper=3.0),
        _parameter("substitution_probability", 0.1, lower=0.0, upper=0.2),
        _parameter("delayed_purchase_probability", 0.1, lower=0.0, upper=0.2),
        _parameter("service_penalty", 0.5, lower=0.0, upper=1.0),
        _parameter("unit_cost", 1.0, lower=0.8, upper=1.2),
        _parameter("disposal_cost", 0.2, lower=0.1, upper=0.4),
        _parameter("handling_cost", 0.1, lower=0.0, upper=0.2),
        _parameter("holding_cost", 0.05, lower=0.0, upper=0.1),
        _parameter("markdown_recovery", 0.0, lower=0.0, upper=0.1),
        _parameter("service_floor", 0.9, lower=0.85, upper=0.95),
        _parameter("order_volatility_cost", 0.05, lower=0.0, upper=0.1),
        _parameter("carbon_externality", 0.02, lower=0.0, upper=0.05),
    ]


def test_effective_date_lookup_uses_most_specific_record() -> None:
    generic = _parameter("unit_cost", 1.0)
    scoped = BusinessParameter(
        **{**generic.__dict__, "value": 2.0, "lower": 2.0, "upper": 2.0, "category_id": "C001"}
    )
    registry = ParameterRegistry([generic, scoped])

    assert registry.lookup("unit_cost", as_of="2026-02-01", category_id="C001").value == 2.0
    assert registry.lookup("unit_cost", as_of="2026-02-01", category_id="C999").value == 1.0


def test_invalid_negative_cost_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        _parameter("unit_cost", -1.0)


def test_currency_conversion_is_explicit_and_isolated() -> None:
    parameter = _parameter("unit_cost", 10.0)

    converted = convert_currency(parameter, target_currency="USD", rates={("EUR", "USD"): 1.2})

    assert converted.value == 12.0
    assert parameter.value == 10.0


def test_critical_fractile_increases_with_underage_cost() -> None:
    base = ParameterRegistry(_parameters())
    high_margin = ParameterRegistry(
        [BusinessParameter(**{**item.__dict__, "value": 4.0, "lower": 4.0, "upper": 4.0}) if item.name == "gross_margin" else item for item in _parameters()]
    )

    assert economic_terms_from_registry(high_margin, as_of="2026-01-01", currency="EUR").critical_fractile() > economic_terms_from_registry(base, as_of="2026-01-01", currency="EUR").critical_fractile()


def test_uncertainty_sampling_is_reproducible() -> None:
    first = sample_parameter_uncertainty(_parameters(), draws=3, seed=5)
    second = sample_parameter_uncertainty(_parameters(), draws=3, seed=5)

    pd.testing.assert_frame_equal(first, second)


def test_tornado_and_policy_stability_outputs() -> None:
    tornado = tornado_sensitivity(_parameters(), target_name="critical_fractile")

    assert "swing" in tornado.columns
    assert classify_policy_stability(pd.Series(["A", "A", "B"]), stable_threshold=0.8) == "unstable"
    assert classify_policy_stability(pd.Series(["A", "A", "A"]), stable_threshold=0.8) == "stable"
