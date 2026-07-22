"""Versioned shelf-life estimation and remaining-life scenario utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray


class ShelfLifeError(ValueError):
    """Raised when batch shelf-life observations are impossible or unsupported."""


@dataclass(frozen=True)
class ShelfLifeDistribution:
    """Discrete remaining-life distribution for one product/supplier context."""

    product_id: str
    supplier_id: str
    support_days: tuple[int, ...]
    probabilities: tuple[float, ...]
    source: str
    sample_size: int
    censored_observations: int = 0

    def __post_init__(self) -> None:
        if len(self.support_days) != len(self.probabilities):
            raise ValueError("Support and probabilities must have the same length")
        if not self.support_days:
            raise ValueError("Distribution support cannot be empty")
        if any(day < 0 for day in self.support_days):
            raise ValueError("Remaining life cannot be negative")
        total = sum(self.probabilities)
        if total <= 0.0:
            raise ValueError("Probabilities must have positive mass")

    def normalised_probabilities(self) -> NDArray[np.float64]:
        """Return probabilities normalized to sum to one."""
        probabilities = np.asarray(self.probabilities, dtype=float)
        normalised: NDArray[np.float64] = probabilities / probabilities.sum()
        return normalised

    def mean(self) -> float:
        """Return expected remaining sellable life."""
        support = np.asarray(self.support_days, dtype=float)
        return float(np.dot(support, self.normalised_probabilities()))

    def quantile(self, probability: float) -> int:
        """Return a discrete quantile of remaining sellable life."""
        if not 0.0 <= probability <= 1.0:
            raise ValueError("Probability must be in [0, 1]")
        cumulative = np.cumsum(self.normalised_probabilities())
        index = int(np.searchsorted(cumulative, probability, side="left"))
        return self.support_days[min(index, len(self.support_days) - 1)]

    def sample(self, n: int, *, seed: int) -> NDArray[np.int64]:
        """Sample remaining-life scenarios deterministically for a seed."""
        if n < 1:
            raise ValueError("Sample size must be positive")
        rng = np.random.default_rng(seed)
        return rng.choice(
            np.asarray(self.support_days, dtype=np.int64),
            size=n,
            replace=True,
            p=self.normalised_probabilities(),
        )


class ShelfLifeModel(Protocol):
    """Interface for shelf-life distribution providers."""

    def distribution_for(self, product_id: str, supplier_id: str, *, season: str | None = None) -> ShelfLifeDistribution:
        """Return a remaining-life distribution for the requested context."""
        ...


def _season(date: pd.Timestamp) -> str:
    month = int(date.month)
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def prepare_shelf_life_observations(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and derive batch-level shelf-life observations without silent repair."""
    required = {"batch_id", "product_id", "supplier_id", "receipt_date"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ShelfLifeError(f"Shelf-life observations are missing columns: {missing}")
    prepared = frame.copy(deep=True)
    prepared["receipt_date"] = pd.to_datetime(prepared["receipt_date"]).dt.normalize()
    for column in ("expiry_date", "pack_date", "last_observed_date"):
        if column in prepared.columns:
            prepared[column] = pd.to_datetime(prepared[column]).dt.normalize()
    if "expiry_date" in prepared.columns:
        delivery_after_expiry = prepared["expiry_date"].notna() & (
            prepared["receipt_date"] > prepared["expiry_date"]
        )
        if bool(delivery_after_expiry.any()):
            raise ShelfLifeError("Receipt date cannot be after expiry date")
        prepared["observed_life_days"] = (
            prepared["expiry_date"] - prepared["receipt_date"]
        ).dt.days
    elif "observed_life_days" not in prepared.columns:
        raise ShelfLifeError("Provide expiry_date or observed_life_days")
    prepared["observed_life_days"] = pd.to_numeric(prepared["observed_life_days"], errors="coerce")
    negative_life = prepared["observed_life_days"].notna() & (prepared["observed_life_days"] < 0)
    if bool(negative_life.any()):
        raise ShelfLifeError("Observed shelf life cannot be negative")
    prepared["right_censored"] = prepared.get("right_censored", False)
    prepared["right_censored"] = prepared["right_censored"].fillna(False).astype(bool)
    prepared["season"] = prepared["receipt_date"].map(_season)
    return prepared.sort_values(["receipt_date", "product_id", "supplier_id", "batch_id"]).reset_index(drop=True)


@dataclass(frozen=True)
class MasterDataShelfLifeModel:
    """Deterministic product-master shelf-life baseline."""

    master_data: pd.DataFrame

    def distribution_for(self, product_id: str, supplier_id: str, *, season: str | None = None) -> ShelfLifeDistribution:
        rows = self.master_data[self.master_data["product_id"] == product_id]
        if rows.empty:
            raise ShelfLifeError(f"No master-data shelf life for {product_id}")
        life = int(pd.to_numeric(rows.iloc[0]["shelf_life_days"]))
        return ShelfLifeDistribution(
            product_id=product_id,
            supplier_id=supplier_id,
            support_days=(life,),
            probabilities=(1.0,),
            source="master_data",
            sample_size=int(rows.shape[0]),
        )


@dataclass(frozen=True)
class ConservativeShelfLifeFallback:
    """Conservative fallback for sparse or conflicting batch evidence."""

    default_life_days: int = 1
    source: str = "conservative_fallback"

    def distribution_for(self, product_id: str, supplier_id: str, *, season: str | None = None) -> ShelfLifeDistribution:
        return ShelfLifeDistribution(
            product_id=product_id,
            supplier_id=supplier_id,
            support_days=(self.default_life_days,),
            probabilities=(1.0,),
            source=self.source,
            sample_size=0,
        )


@dataclass(frozen=True)
class EmpiricalShelfLifeModel:
    """Empirical shelf-life distribution by product, supplier, and season."""

    observations: pd.DataFrame
    fallback: ShelfLifeModel
    min_samples: int = 3

    @classmethod
    def fit(
        cls,
        observations: pd.DataFrame,
        *,
        fallback: ShelfLifeModel,
        min_samples: int = 3,
    ) -> EmpiricalShelfLifeModel:
        """Fit an empirical distribution from validated observations."""
        if min_samples < 1:
            raise ValueError("Minimum samples must be positive")
        return cls(
            observations=prepare_shelf_life_observations(observations),
            fallback=fallback,
            min_samples=min_samples,
        )

    def distribution_for(self, product_id: str, supplier_id: str, *, season: str | None = None) -> ShelfLifeDistribution:
        candidates = self.observations[
            (self.observations["product_id"] == product_id)
            & (self.observations["supplier_id"] == supplier_id)
        ]
        if season is not None:
            seasonal = candidates[candidates["season"] == season]
            if int(seasonal.shape[0]) >= self.min_samples:
                candidates = seasonal
        uncensored = candidates[~candidates["right_censored"]]
        if int(uncensored.shape[0]) < self.min_samples:
            return self.fallback.distribution_for(product_id, supplier_id, season=season)
        life = pd.to_numeric(uncensored["observed_life_days"], errors="coerce").dropna().astype(int)
        counts = life.value_counts().sort_index()
        return ShelfLifeDistribution(
            product_id=product_id,
            supplier_id=supplier_id,
            support_days=tuple(int(index) for index in counts.index),
            probabilities=tuple(float(value) for value in counts.to_numpy()),
            source="empirical_product_supplier_season",
            sample_size=int(uncensored.shape[0]),
            censored_observations=int(candidates["right_censored"].sum()),
        )


def attach_shelf_life_distributions(
    frame: pd.DataFrame,
    model: ShelfLifeModel,
    *,
    season_column: str | None = "season",
) -> pd.DataFrame:
    """Attach distribution metadata to ordering rows."""
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        season = str(row[season_column]) if season_column is not None and season_column in frame.columns else None
        distribution = model.distribution_for(str(row["product_id"]), str(row["supplier_id"]), season=season)
        record: dict[str, object] = {str(key): value for key, value in row.items()}
        rows.append(
            {
                **record,
                "shelf_life_distribution_source": distribution.source,
                "shelf_life_sample_size": distribution.sample_size,
                "expected_remaining_life_days": distribution.mean(),
                "p10_remaining_life_days": distribution.quantile(0.10),
                "p90_remaining_life_days": distribution.quantile(0.90),
            }
        )
    return pd.DataFrame(rows)


def expand_batch_life_scenarios(
    batches: pd.DataFrame,
    model: ShelfLifeModel,
    *,
    scenarios: int,
    seed: int,
) -> pd.DataFrame:
    """Sample remaining-life scenarios for each batch while preserving quantity."""
    rows: list[dict[str, object]] = []
    for batch_index, (_, row) in enumerate(batches.reset_index(drop=True).iterrows()):
        distribution = model.distribution_for(str(row["product_id"]), str(row["supplier_id"]))
        sampled = distribution.sample(scenarios, seed=seed + batch_index)
        for scenario_id, life in enumerate(sampled):
            rows.append(
                {
                    "batch_id": row["batch_id"],
                    "scenario_id": scenario_id,
                    "product_id": row["product_id"],
                    "supplier_id": row["supplier_id"],
                    "quantity": row["quantity"],
                    "sampled_remaining_life_days": int(life),
                    "distribution_source": distribution.source,
                }
            )
    return pd.DataFrame(rows).sort_values(["scenario_id", "batch_id"], ignore_index=True)


def build_shelf_life_diagnostics(observations: pd.DataFrame) -> pd.DataFrame:
    """Report calibration inputs by product, supplier, and season."""
    prepared = prepare_shelf_life_observations(observations)
    rows: list[dict[str, object]] = []
    for keys, group in prepared.groupby(["product_id", "supplier_id", "season"], sort=True):
        product_id, supplier_id, season = keys
        life = pd.to_numeric(group["observed_life_days"], errors="coerce").dropna()
        rows.append(
            {
                "product_id": product_id,
                "supplier_id": supplier_id,
                "season": season,
                "batches": int(group.shape[0]),
                "right_censored_batches": int(group["right_censored"].sum()),
                "median_life_days": float(life.median()) if not life.empty else 0.0,
                "p10_life_days": float(life.quantile(0.10)) if not life.empty else 0.0,
                "p90_life_days": float(life.quantile(0.90)) if not life.empty else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["product_id", "supplier_id", "season"], ignore_index=True)


def compare_fixed_vs_stochastic_shelf_life(
    frame: pd.DataFrame,
    model: ShelfLifeModel,
    *,
    fixed_life_column: str = "shelf_life_days",
    risk_horizon_days: int = 2,
) -> pd.DataFrame:
    """Compare fixed-life expiry risk with stochastic distribution risk."""
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        distribution = model.distribution_for(str(row["product_id"]), str(row["supplier_id"]))
        fixed_life = int(row[fixed_life_column])
        stochastic_risk = float(
            distribution.normalised_probabilities()[
                np.asarray(distribution.support_days) <= risk_horizon_days
            ].sum()
        )
        rows.append(
            {
                "product_id": row["product_id"],
                "supplier_id": row["supplier_id"],
                "fixed_expiry_risk": float(fixed_life <= risk_horizon_days),
                "stochastic_expiry_risk": stochastic_risk,
                "expected_remaining_life_days": distribution.mean(),
                "distribution_source": distribution.source,
            }
        )
    return pd.DataFrame(rows)
