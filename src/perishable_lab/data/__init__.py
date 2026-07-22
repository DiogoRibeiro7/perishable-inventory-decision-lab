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
from perishable_lab.data.public_retail import (
    M5AdapterConfig,
    PublicBenchmarkConfig,
    check_date_completeness,
    known_m5_leakage_fields,
    load_m5_canonical,
    public_dataset_candidates,
    run_public_retail_benchmark,
    validate_m5_files,
)

__all__ = [
    "BigQueryRetailAdapter",
    "DailyRetailInputs",
    "DataContractError",
    "LocalFileRetailAdapter",
    "M5AdapterConfig",
    "PublicBenchmarkConfig",
    "RetailTableAdapter",
    "build_canonical_daily_demand",
    "check_date_completeness",
    "deduplicate_versioned_events",
    "known_m5_leakage_fields",
    "load_m5_canonical",
    "public_dataset_candidates",
    "run_public_retail_benchmark",
    "validate_m5_files",
]
