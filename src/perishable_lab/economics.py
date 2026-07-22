"""Versioned business-parameter registry and economic sensitivity utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal, cast

import numpy as np
import pandas as pd

ParameterSource = Literal["observed", "estimated", "elicited", "assumed"]


@dataclass(frozen=True)
class BusinessParameter:
    """Auditable economic parameter with scope, ownership, and uncertainty."""

    name: str
    value: float
    lower: float
    upper: float
    unit: str
    currency: str | None
    owner: str
    source: ParameterSource
    effective_from: date
    effective_to: date | None = None
    retailer_id: str | None = None
    category_id: str | None = None
    store_type: str | None = None

    def __post_init__(self) -> None:
        if self.value < 0.0 or self.lower < 0.0 or self.upper < 0.0:
            raise ValueError("Business parameters cannot be negative")
        if self.lower > self.value or self.value > self.upper:
            raise ValueError("Parameter value must lie within the confidence range")
        if self.unit.endswith("_probability") and self.upper > 1.0:
            raise ValueError("Probability parameters must be bounded by one")


@dataclass(frozen=True)
class EconomicTerms:
    """Financial objective terms plus separately reported externality."""

    underage_cost: float
    overage_cost: float
    service_floor: float
    order_volatility_cost: float
    carbon_externality: float
    currency: str

    def critical_fractile(self) -> float:
        denominator = self.underage_cost + self.overage_cost
        if denominator <= 0.0:
            return 0.5
        return min(max(self.underage_cost / denominator, 0.01), 0.99)


class ParameterRegistry:
    """Versioned lookup for retailer/category/store-type parameters."""

    def __init__(self, parameters: list[BusinessParameter]) -> None:
        if not parameters:
            raise ValueError("At least one business parameter is required")
        self._frame = pd.DataFrame([asdict(parameter) for parameter in parameters])
        self._frame["effective_from"] = pd.to_datetime(self._frame["effective_from"]).dt.normalize()
        self._frame["effective_to"] = pd.to_datetime(self._frame["effective_to"]).dt.normalize()

    @property
    def frame(self) -> pd.DataFrame:
        return self._frame.copy(deep=True)

    def lookup(
        self,
        name: str,
        *,
        as_of: date | str,
        retailer_id: str | None = None,
        category_id: str | None = None,
        store_type: str | None = None,
    ) -> BusinessParameter:
        """Return the most specific parameter active on a date."""
        as_of_ts = pd.Timestamp(as_of).normalize()
        candidates = self._frame[
            (self._frame["name"] == name)
            & (self._frame["effective_from"] <= as_of_ts)
            & (self._frame["effective_to"].isna() | (self._frame["effective_to"] >= as_of_ts))
        ].copy()
        if candidates.empty:
            raise KeyError(f"No active parameter named {name}")
        for column, value in (
            ("retailer_id", retailer_id),
            ("category_id", category_id),
            ("store_type", store_type),
        ):
            if value is not None:
                scoped = candidates[(candidates[column].isna()) | (candidates[column] == value)]
                candidates = scoped
        candidates["_specificity"] = candidates[["retailer_id", "category_id", "store_type"]].notna().sum(axis=1)
        best = candidates.sort_values(["_specificity", "effective_from"], ascending=[False, False]).iloc[0]
        effective_to = (
            None
            if pd.isna(best["effective_to"])
            else pd.Timestamp(best["effective_to"]).date()
        )
        return BusinessParameter(
            name=str(best["name"]),
            value=float(best["value"]),
            lower=float(best["lower"]),
            upper=float(best["upper"]),
            unit=str(best["unit"]),
            currency=None if pd.isna(best["currency"]) else str(best["currency"]),
            owner=str(best["owner"]),
            source=cast(ParameterSource, str(best["source"])),
            effective_from=pd.Timestamp(best["effective_from"]).date(),
            effective_to=effective_to,
            retailer_id=None if pd.isna(best["retailer_id"]) else str(best["retailer_id"]),
            category_id=None if pd.isna(best["category_id"]) else str(best["category_id"]),
            store_type=None if pd.isna(best["store_type"]) else str(best["store_type"]),
        )


def convert_currency(
    parameter: BusinessParameter,
    *,
    target_currency: str,
    rates: dict[tuple[str, str], float],
) -> BusinessParameter:
    """Convert a monetary parameter only when an explicit exchange rate is provided."""
    if parameter.currency is None or parameter.currency == target_currency:
        return parameter
    rate = rates[(parameter.currency, target_currency)]
    return BusinessParameter(
        **{
            **asdict(parameter),
            "value": parameter.value * rate,
            "lower": parameter.lower * rate,
            "upper": parameter.upper * rate,
            "currency": target_currency,
        }
    )


def economic_terms_from_registry(
    registry: ParameterRegistry,
    *,
    as_of: date | str,
    currency: str,
    retailer_id: str | None = None,
    category_id: str | None = None,
    store_type: str | None = None,
) -> EconomicTerms:
    """Build objective terms from explicit parameter records."""

    def value(name: str) -> float:
        return registry.lookup(
            name,
            as_of=as_of,
            retailer_id=retailer_id,
            category_id=category_id,
            store_type=store_type,
        ).value

    gross_margin = value("gross_margin")
    substitution_probability = value("substitution_probability")
    delayed_purchase_probability = value("delayed_purchase_probability")
    service_penalty = value("service_penalty")
    underage = gross_margin * (1.0 - substitution_probability - delayed_purchase_probability) + service_penalty
    overage = (
        value("unit_cost")
        + value("disposal_cost")
        + value("handling_cost")
        + value("holding_cost")
        - value("markdown_recovery")
    )
    return EconomicTerms(
        underage_cost=max(0.0, underage),
        overage_cost=max(0.0, overage),
        service_floor=value("service_floor"),
        order_volatility_cost=value("order_volatility_cost"),
        carbon_externality=value("carbon_externality"),
        currency=currency,
    )


def sample_parameter_uncertainty(
    parameters: list[BusinessParameter],
    *,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    """Sample parameter uncertainty reproducibly from confidence ranges."""
    if draws < 1:
        raise ValueError("Draw count must be positive")
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for draw in range(draws):
        row: dict[str, object] = {"draw": draw}
        for parameter in parameters:
            row[parameter.name] = float(rng.uniform(parameter.lower, parameter.upper))
        rows.append(row)
    return pd.DataFrame(rows)


def tornado_sensitivity(
    base_parameters: list[BusinessParameter],
    *,
    target_name: str,
) -> pd.DataFrame:
    """Return one-at-a-time critical-fractile sensitivity by parameter range."""
    rows: list[dict[str, object]] = []
    for parameter in base_parameters:
        low_params = [
            BusinessParameter(**{**asdict(item), "value": item.lower if item.name == parameter.name else item.value})
            for item in base_parameters
        ]
        high_params = [
            BusinessParameter(**{**asdict(item), "value": item.upper if item.name == parameter.name else item.value})
            for item in base_parameters
        ]
        low_registry = ParameterRegistry(low_params)
        high_registry = ParameterRegistry(high_params)
        low_terms = economic_terms_from_registry(low_registry, as_of=parameter.effective_from, currency="EUR")
        high_terms = economic_terms_from_registry(high_registry, as_of=parameter.effective_from, currency="EUR")
        rows.append(
            {
                "parameter": parameter.name,
                f"{target_name}_low": low_terms.critical_fractile(),
                f"{target_name}_high": high_terms.critical_fractile(),
                "swing": abs(high_terms.critical_fractile() - low_terms.critical_fractile()),
            }
        )
    return pd.DataFrame(rows).sort_values("swing", ascending=False, ignore_index=True)


def classify_policy_stability(policy_winners: pd.Series, *, stable_threshold: float = 0.8) -> str:
    """Classify whether a policy recommendation survives parameter uncertainty."""
    shares = policy_winners.value_counts(normalize=True)
    if shares.empty:
        return "unstable"
    return "stable" if float(shares.iloc[0]) >= stable_threshold else "unstable"
