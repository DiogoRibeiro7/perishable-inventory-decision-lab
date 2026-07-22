"""Shelf-life uncertainty models and batch-level utilities."""

from perishable_lab.shelf_life.models import (
    ConservativeShelfLifeFallback,
    EmpiricalShelfLifeModel,
    MasterDataShelfLifeModel,
    ShelfLifeDistribution,
    ShelfLifeError,
    attach_shelf_life_distributions,
    build_shelf_life_diagnostics,
    compare_fixed_vs_stochastic_shelf_life,
    expand_batch_life_scenarios,
    prepare_shelf_life_observations,
)

__all__ = [
    "ConservativeShelfLifeFallback",
    "EmpiricalShelfLifeModel",
    "MasterDataShelfLifeModel",
    "ShelfLifeDistribution",
    "ShelfLifeError",
    "attach_shelf_life_distributions",
    "build_shelf_life_diagnostics",
    "compare_fixed_vs_stochastic_shelf_life",
    "expand_batch_life_scenarios",
    "prepare_shelf_life_observations",
]
