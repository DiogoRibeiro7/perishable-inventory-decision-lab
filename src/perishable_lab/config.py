"""Typed configuration objects for the project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class SimulationConfig(BaseModel):
    """Configuration for synthetic demand generation."""

    days: int = Field(default=240, ge=60)
    stores: int = Field(default=5, ge=1)
    products: int = Field(default=16, ge=1)
    seed: int = 42


class ForecastConfig(BaseModel):
    """Configuration for distributional forecasting."""

    quantiles: tuple[float, ...] = (0.05, 0.1, 0.5, 0.9, 0.95)
    max_iter: int = Field(default=120, ge=10)
    learning_rate: float = Field(default=0.08, gt=0.0)
    max_leaf_nodes: int = Field(default=24, ge=2)
    min_samples_leaf: int = Field(default=20, ge=2)

    @field_validator("quantiles")
    @classmethod
    def validate_quantiles(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        """Ensure ordered, unique probabilities strictly inside the unit interval."""
        if len(value) < 3:
            raise ValueError("At least three quantiles are required")
        if tuple(sorted(set(value))) != value:
            raise ValueError("Quantiles must be unique and sorted")
        if value[0] <= 0.0 or value[-1] >= 1.0:
            raise ValueError("Quantiles must be strictly between zero and one")
        return value


class InventoryConfig(BaseModel):
    """Configuration for policy evaluation."""

    service_level: float = Field(default=0.9, gt=0.5, lt=1.0)
    holding_cost_per_unit_day: float = Field(default=0.03, ge=0.0)
    default_lead_time_days: int = Field(default=1, ge=0, le=7)


class MonitoringConfig(BaseModel):
    """Thresholds for operational health checks."""

    minimum_coverage: float = Field(default=0.75, gt=0.0, le=1.0)
    maximum_missing_rate: float = Field(default=0.02, ge=0.0, lt=1.0)
    maximum_pinball_degradation: float = Field(default=0.20, ge=0.0)


class AppConfig(BaseModel):
    """Complete application configuration."""

    simulation: SimulationConfig = SimulationConfig()
    forecasting: ForecastConfig = ForecastConfig()
    inventory: InventoryConfig = InventoryConfig()
    monitoring: MonitoringConfig = MonitoringConfig()


def load_config(path: Path) -> AppConfig:
    """Load and validate a YAML configuration file.

    Args:
        path: Existing YAML configuration path.

    Returns:
        Validated application configuration.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML root is not a mapping.
    """
    raw: Any
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a mapping")
    return AppConfig.model_validate(raw)
