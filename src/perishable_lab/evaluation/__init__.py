"""Evaluation split and reporting utilities."""

from perishable_lab.evaluation.reporting import (
    build_evaluation_report,
    paired_block_bootstrap_difference,
)
from perishable_lab.evaluation.simulator_vv import (
    build_parameter_manifest,
    build_validation_gate,
    check_simulation_invariants,
    summarise_sensitivity,
)

__all__ = [
    "build_evaluation_report",
    "build_parameter_manifest",
    "build_validation_gate",
    "check_simulation_invariants",
    "paired_block_bootstrap_difference",
    "summarise_sensitivity",
]
