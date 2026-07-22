"""Reference solution for the take-home case study."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from perishable_lab.forecasting.baselines import SeasonalNaiveQuantileForecaster
from perishable_lab.inventory.policies import (
    OrderingConstraints,
    PolicyContext,
    apply_ordering_constraints,
)

KEYS = ["date", "store_id", "product_id"]


def _read_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "sales": pd.read_csv(data_dir / "sales.csv", parse_dates=["date", "known_at"]),
        "inventory": pd.read_csv(data_dir / "inventory_snapshots.csv", parse_dates=["date", "snapshot_time"]),
        "prices": pd.read_csv(data_dir / "prices.csv", parse_dates=["date", "known_at"]),
        "promotions": pd.read_csv(data_dir / "promotions.csv", parse_dates=["date", "known_at"]),
        "products": pd.read_csv(data_dir / "products.csv"),
    }


def _dedupe_sales(sales: pd.DataFrame) -> pd.DataFrame:
    prepared = sales.copy()
    prepared["sold_units"] = prepared["sold_units"].clip(lower=0)
    prepared["transaction_count"] = prepared["transaction_count"].clip(lower=0)
    return (
        prepared.sort_values([*KEYS, "known_at"])
        .drop_duplicates(KEYS, keep="last")
        .sort_values(KEYS)
        .reset_index(drop=True)
    )


def _latest_known(frame: pd.DataFrame, cutoff_hour: int = 6) -> pd.DataFrame:
    prepared = frame.copy()
    cutoff = prepared["date"] + pd.Timedelta(hours=cutoff_hour)
    prepared = prepared.loc[prepared["known_at"] <= cutoff]
    return (
        prepared.sort_values([*KEYS, "known_at"])
        .drop_duplicates(KEYS, keep="last")
        .drop(columns=["known_at"])
        .reset_index(drop=True)
    )


def build_training_frame(data_dir: Path) -> pd.DataFrame:
    """Build leakage-safe daily rows from public exercise files."""
    data = _read_data(data_dir)
    sales = _dedupe_sales(data["sales"]).rename(columns={"sold_units": "demand"})
    inventory = data["inventory"].copy()
    inventory["observed_inventory"] = inventory["observed_inventory"].clip(lower=0)
    inventory = inventory.sort_values([*KEYS, "snapshot_time"]).drop_duplicates(KEYS, keep="last")
    inventory = inventory.drop(columns=["snapshot_time"])
    prices = _latest_known(data["prices"])
    promotions = _latest_known(data["promotions"])

    frame = (
        sales.merge(inventory, on=KEYS, how="left", validate="one_to_one")
        .merge(prices, on=KEYS, how="left", validate="one_to_one")
        .merge(promotions, on=KEYS, how="left", validate="one_to_one")
        .merge(data["products"], on="product_id", how="left", validate="many_to_one")
    )
    frame["promotion_flag"] = frame["promotion_flag"].fillna(0).astype(int)
    frame["discount"] = frame["discount"].fillna(0.0)
    frame["observed_inventory"] = frame["observed_inventory"].fillna(0.0)
    return frame.sort_values(KEYS).reset_index(drop=True)


def _split_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(frame["date"].unique())
    split_date = dates[int(len(dates) * 0.70)]
    train = frame.loc[frame["date"] < split_date].copy()
    test = frame.loc[frame["date"] >= split_date].copy()
    return train, test


def _make_recommendations(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    forecaster = SeasonalNaiveQuantileForecaster(quantiles=(0.5, 0.8), min_history=4).fit(train)
    forecasts = forecaster.predict(test)
    scored = pd.concat([test.reset_index(drop=True), forecasts.reset_index(drop=True)], axis=1)
    rows: list[dict[str, object]] = []
    for _, row in scored.iterrows():
        context = PolicyContext(
            forecast_target=float(row["q80"]) * max(1, int(row["lead_time_days"])),
            forecast_median=float(row["q50"]),
            observed_inventory=float(row["observed_inventory"]),
            pipeline_inventory=0.0,
            lead_time_days=int(row["lead_time_days"]),
            shelf_life_days=int(row["shelf_life_days"]),
        )
        requested = round(context.forecast_target - context.observed_inventory)
        quantity = apply_ordering_constraints(
            requested,
            context,
            OrderingConstraints(
                case_pack=int(row["case_pack"]),
                minimum_order_quantity=int(row["minimum_order_quantity"]),
                storage_capacity_units=int(row["storage_capacity_units"]),
            ),
        )
        rows.append(
            {
                "date": row["date"].date().isoformat(),
                "store_id": row["store_id"],
                "product_id": row["product_id"],
                "q50": round(float(row["q50"]), 3),
                "q80": round(float(row["q80"]), 3),
                "recommended_order_units": int(quantity),
                "assumption_note": "seasonal empirical baseline with public inventory only",
            }
        )
    return pd.DataFrame(rows)


def _score_against_truth(
    recommendations: pd.DataFrame,
    truth: pd.DataFrame,
    products: pd.DataFrame,
) -> dict[str, float]:
    joined = (
        recommendations.merge(truth, on=KEYS, how="left", validate="one_to_one")
        .merge(products, on="product_id", how="left", validate="many_to_one")
    )
    fulfilled = joined[["recommended_order_units", "true_demand"]].min(axis=1)
    lost = (joined["true_demand"] - fulfilled).clip(lower=0)
    waste = (joined["recommended_order_units"] - joined["true_demand"]).clip(lower=0)
    cost = (
        lost * joined["unit_margin"]
        + waste * (joined["unit_cost"] + joined["waste_cost"])
        + joined["recommended_order_units"] * 0.01
    )
    demand = float(joined["true_demand"].sum())
    return {
        "true_demand_units": demand,
        "fulfilled_units": float(fulfilled.sum()),
        "lost_sales_units": float(lost.sum()),
        "waste_units": float(waste.sum()),
        "fill_rate": float(fulfilled.sum() / max(demand, 1.0)),
        "waste_rate": float(waste.sum() / max(joined["recommended_order_units"].sum(), 1.0)),
        "total_cost": float(cost.sum()),
    }


def run_reference_solution(data_dir: Path, output_dir: Path) -> dict[str, Path]:
    """Run the baseline solution and write submission-style outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = build_training_frame(data_dir)
    train, test = _split_frame(frame)
    recommendations = _make_recommendations(train, test)
    truth = pd.read_csv(data_dir / "evaluator_only" / "hidden_truth.csv")
    products = pd.read_csv(data_dir / "products.csv")
    truth = truth.loc[truth["date"].isin(recommendations["date"])]
    metrics = _score_against_truth(recommendations, truth, products)

    recommendations.to_csv(output_dir / "recommendations.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "audit_assumptions.md").write_text(_audit_text(frame), encoding="utf-8")
    return {
        "recommendations": output_dir / "recommendations.csv",
        "metrics": output_dir / "metrics.json",
        "audit": output_dir / "audit_assumptions.md",
    }


def _audit_text(frame: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Data Audit and Assumptions",
            "",
            f"- Rows after key cleanup: {len(frame)}.",
            "- Duplicate sales keys keep the latest known record.",
            "- Negative observed inventory is clipped to zero and listed as a source issue.",
            "- Promotions are included only when known by the 06:00 planning cutoff.",
            "- The baseline uses public sales history only; evaluator-only demand is used only for scoring.",
            "- The order rule is intentionally simple so the trade-offs are easy to defend.",
            "",
        ]
    )
