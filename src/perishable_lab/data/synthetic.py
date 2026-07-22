"""Synthetic fresh-grocery demand generation.

The generator creates a controlled but non-trivial environment with product and
store heterogeneity, weekly and annual seasonality, promotions, price effects,
intermittent demand, weather-like shocks, and negative-binomial overdispersion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray


@dataclass(frozen=True)
class SyntheticDataSpec:
    """Parameters controlling the synthetic panel."""

    days: int = 240
    stores: int = 5
    products: int = 16
    seed: int = 42
    start_date: str = "2025-01-01"


def _negative_binomial_from_mean(
    rng: np.random.Generator,
    mean: NDArray[np.float64],
    dispersion: float,
) -> NDArray[np.int64]:
    """Sample a negative-binomial variable from a mean/dispersion parameterisation."""
    safe_mean = np.maximum(mean, 1e-6)
    probability = dispersion / (dispersion + safe_mean)
    return rng.negative_binomial(dispersion, probability).astype(np.int64)


def generate_daily_demand(spec: SyntheticDataSpec) -> pd.DataFrame:
    """Generate a store-product-day fresh-grocery panel.

    Args:
        spec: Generation settings.

    Returns:
        Data frame sorted by store, product, and date.
    """
    if spec.days < 60:
        raise ValueError("At least 60 days are required for lagged evaluation")
    if spec.stores < 1 or spec.products < 1:
        raise ValueError("Stores and products must be positive")

    rng = np.random.default_rng(spec.seed)
    dates = pd.date_range(spec.start_date, periods=spec.days, freq="D")

    product_base = rng.lognormal(mean=2.15, sigma=0.55, size=spec.products)
    store_scale = rng.lognormal(mean=0.0, sigma=0.22, size=spec.stores)
    shelf_lives = rng.integers(2, 9, size=spec.products)
    lead_times = rng.choice(np.array([1, 1, 1, 2]), size=spec.products)
    unit_costs = rng.uniform(0.4, 3.5, size=spec.products)
    unit_margins = rng.uniform(0.3, 2.8, size=spec.products)
    waste_costs = rng.uniform(0.05, 0.5, size=spec.products)
    price_elasticity = rng.uniform(-1.8, -0.4, size=spec.products)
    intermittent = rng.random(spec.products) < 0.18

    rows: list[dict[str, object]] = []
    global_shock = rng.normal(0.0, 0.08, size=spec.days)

    for store_idx in range(spec.stores):
        local_shock = rng.normal(0.0, 0.06, size=spec.days)
        for product_idx in range(spec.products):
            base_price = unit_costs[product_idx] + unit_margins[product_idx]
            promo = rng.random(spec.days) < 0.10
            discount = np.where(promo, rng.uniform(0.08, 0.28, size=spec.days), 0.0)
            observed_price = base_price * (1.0 - discount)

            day_of_week = dates.dayofweek.to_numpy()
            weekly = 1.0 + 0.18 * np.sin(2.0 * np.pi * day_of_week / 7.0 + product_idx / 4.0)
            annual = 1.0 + 0.10 * np.sin(2.0 * np.pi * np.arange(spec.days) / 365.25)
            promo_effect = np.where(promo, 1.0 + rng.uniform(0.25, 0.80, spec.days), 1.0)
            relative_price = observed_price / base_price
            price_effect = np.power(relative_price, price_elasticity[product_idx])
            shock = np.exp(global_shock + local_shock)

            mean = (
                product_base[product_idx]
                * store_scale[store_idx]
                * weekly
                * annual
                * promo_effect
                * price_effect
                * shock
            )
            if intermittent[product_idx]:
                zero_probability = rng.uniform(0.20, 0.55)
                mean = np.where(rng.random(spec.days) < zero_probability, 0.03, mean * 0.55)

            demand = _negative_binomial_from_mean(rng, mean.astype(np.float64), dispersion=8.0)
            shrinkage_rate = rng.uniform(0.002, 0.025, size=spec.days)
            record_error_std = rng.uniform(0.0, 1.8, size=spec.days)

            for day_idx, date in enumerate(dates):
                rows.append(
                    {
                        "date": date,
                        "store_id": f"S{store_idx:03d}",
                        "product_id": f"P{product_idx:04d}",
                        "demand": int(demand[day_idx]),
                        "price": float(observed_price[day_idx]),
                        "promotion": int(promo[day_idx]),
                        "shelf_life_days": int(shelf_lives[product_idx]),
                        "lead_time_days": int(lead_times[product_idx]),
                        "unit_cost": float(unit_costs[product_idx]),
                        "unit_margin": float(unit_margins[product_idx]),
                        "waste_cost": float(waste_costs[product_idx]),
                        "shrinkage_rate": float(shrinkage_rate[day_idx]),
                        "record_error_std": float(record_error_std[day_idx]),
                    }
                )

    frame = pd.DataFrame(rows)
    return frame.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)
