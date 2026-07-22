"""Data generation, ingestion, and validation utilities."""

from perishable_lab.data.adapters import (
    BigQueryRetailAdapter,
    LocalFileRetailAdapter,
    RetailTableAdapter,
)
from perishable_lab.data.canonical import (
    DailyRetailInputs,
    DataContractError,
    build_canonical_daily_demand,
    deduplicate_versioned_events,
)

__all__ = [
    "BigQueryRetailAdapter",
    "DailyRetailInputs",
    "DataContractError",
    "LocalFileRetailAdapter",
    "RetailTableAdapter",
    "build_canonical_daily_demand",
    "deduplicate_versioned_events",
]
