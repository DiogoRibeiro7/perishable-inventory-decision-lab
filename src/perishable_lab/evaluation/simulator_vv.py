"""Simulator verification, validation, and calibration helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def check_simulation_invariants(frame: pd.DataFrame, *, tolerance: float = 1e-9) -> pd.DataFrame:
    """Return event-level simulator invariant violations."""
    issues: list[dict[str, object]] = []
    for index, (_, row) in enumerate(frame.reset_index(drop=True).iterrows()):
        if abs((float(row["fulfilled"]) + float(row["lost_sales"])) - float(row["demand"])) > tolerance:
            issues.append(_issue(index, row, "demand_conservation", "Fulfilled plus lost sales must equal demand."))
        if float(row["fulfilled"]) - float(row["demand"]) > tolerance:
            issues.append(_issue(index, row, "fulfilled_exceeds_demand", "Fulfilled demand cannot exceed demand."))
        if float(row["fulfilled"]) - float(row["opening_inventory"]) > tolerance:
            issues.append(_issue(index, row, "fulfilled_exceeds_stock", "Fulfilled demand cannot exceed opening stock."))
        if abs(float(row["opening_inventory"]) - float(row["fulfilled"]) - float(row["ending_inventory"])) > tolerance:
            issues.append(_issue(index, row, "stock_conservation", "Opening stock must equal fulfilled units plus ending stock."))
        if abs(float(row["expired_units"]) + float(row["shrinkage_units"]) - float(row["waste_units"])) > tolerance:
            issues.append(_issue(index, row, "waste_conservation", "Waste must equal expiry plus shrinkage."))
        if float(row["ending_inventory"]) < -tolerance:
            issues.append(_issue(index, row, "negative_ending_inventory", "Ending inventory cannot be negative."))
        if float(row["order_quantity"]) < -tolerance:
            issues.append(_issue(index, row, "negative_order", "Order quantity cannot be negative."))
        if float(row["supplier_filled_quantity"]) - float(row["order_quantity"]) > tolerance:
            issues.append(_issue(index, row, "supplier_overfill", "Supplier fill cannot exceed ordered quantity."))
    if not issues:
        return pd.DataFrame(columns=["row_index", "date", "rule_id", "message"])
    return pd.DataFrame(issues).sort_values(["row_index", "rule_id"], ignore_index=True)


def _issue(index: int, row: pd.Series, rule_id: str, message: str) -> dict[str, object]:
    return {"row_index": index, "date": row.get("date"), "rule_id": rule_id, "message": message}


def build_parameter_manifest(parameters: dict[str, Any]) -> dict[str, object]:
    """Build an immutable parameter manifest with a deterministic checksum."""
    payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "schema_version": "1.0",
        "parameters": parameters,
        "checksum": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def build_validation_gate(
    invariant_issues: pd.DataFrame,
    *,
    conceptual_validity: str,
    predictive_validity: str,
) -> dict[str, object]:
    """Return a machine-readable simulator validation status gate."""
    software_status = "pass" if invariant_issues.empty else "fail"
    return {
        "schema_version": "1.0",
        "software_verification": software_status,
        "conceptual_validity": conceptual_validity,
        "predictive_validity": predictive_validity,
        "ready_for_policy_claims": software_status == "pass"
        and conceptual_validity == "validated"
        and predictive_validity == "validated",
        "invariant_issue_count": int(invariant_issues.shape[0]),
    }


def summarise_sensitivity(
    runs: pd.DataFrame,
    *,
    parameter_columns: tuple[str, ...],
    kpi_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Summarise KPI uncertainty intervals by sensitivity parameter setting."""
    rows: list[dict[str, object]] = []
    for keys, group in runs.groupby(list(parameter_columns), sort=True):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        record: dict[str, object] = {
            column: value for column, value in zip(parameter_columns, key_tuple, strict=True)
        }
        for kpi in kpi_columns:
            values = pd.to_numeric(group[kpi], errors="coerce")
            record[f"{kpi}_p05"] = float(values.quantile(0.05))
            record[f"{kpi}_median"] = float(values.quantile(0.50))
            record[f"{kpi}_p95"] = float(values.quantile(0.95))
        rows.append(record)
    return pd.DataFrame(rows).sort_values(list(parameter_columns), ignore_index=True)
