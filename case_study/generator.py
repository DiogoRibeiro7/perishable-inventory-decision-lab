"""Generate a compact take-home dataset with intentional data issues."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CaseStudySpec:
    """Controls for the take-home exercise dataset."""

    days: int = 84
    stores: int = 2
    products: int = 4
    seed: int = 1307
    start_date: str = "2026-01-05"

    def __post_init__(self) -> None:
        if self.days < 56:
            raise ValueError("At least 56 days are required for train and test periods")
        if self.stores < 1 or self.products < 1:
            raise ValueError("Stores and products must be positive")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def generate_case_study_data(output_dir: Path, spec: CaseStudySpec | None = None) -> dict[str, str]:
    """Write exercise input files and evaluator-only truth to ``output_dir``."""
    effective_spec = spec or CaseStudySpec()
    rng = np.random.default_rng(effective_spec.seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    dates = pd.date_range(effective_spec.start_date, periods=effective_spec.days, freq="D")
    stores = [f"S{idx + 1:02d}" for idx in range(effective_spec.stores)]
    products = [f"P{idx + 1:03d}" for idx in range(effective_spec.products)]

    product_rows: list[dict[str, object]] = []
    for product_index, product_id in enumerate(products):
        unit_cost = round(float(rng.uniform(0.8, 2.8)), 2)
        product_rows.append(
            {
                "product_id": product_id,
                "category": ["berries", "salads", "prepared", "bakery"][product_index % 4],
                "shelf_life_days": int(rng.integers(2, 6)),
                "lead_time_days": int(rng.choice([1, 1, 2])),
                "case_pack": int(rng.choice([4, 6, 8])),
                "minimum_order_quantity": int(rng.choice([0, 4, 6])),
                "storage_capacity_units": int(rng.choice([36, 48, 60])),
                "unit_cost": unit_cost,
                "unit_margin": round(float(rng.uniform(0.7, 2.4)), 2),
                "waste_cost": round(float(rng.uniform(0.05, 0.35)), 2),
            }
        )
    products_frame = pd.DataFrame(product_rows)

    sales_rows: list[dict[str, object]] = []
    truth_rows: list[dict[str, object]] = []
    inventory_rows: list[dict[str, object]] = []
    delivery_rows: list[dict[str, object]] = []
    waste_rows: list[dict[str, object]] = []
    price_rows: list[dict[str, object]] = []
    promo_rows: list[dict[str, object]] = []

    for store_index, store_id in enumerate(stores):
        store_scale = 1.0 + 0.18 * store_index
        for product_index, product_id in enumerate(products):
            product = products_frame.loc[products_frame["product_id"] == product_id].iloc[0]
            base_price = float(product["unit_cost"]) + float(product["unit_margin"])
            on_hand = int(rng.integers(8, 18))
            for day_index, date in enumerate(dates):
                weekday = int(date.dayofweek)
                planned_promo = day_index % (13 + product_index) == 3
                discount = 0.18 if planned_promo else 0.0
                price = round(base_price * (1.0 - discount), 2)
                seasonal = 1.0 + 0.20 * np.sin(2.0 * np.pi * weekday / 7.0)
                trend = 1.0 + day_index / (effective_spec.days * 7.0)
                promo_lift = 1.45 if planned_promo else 1.0
                mean = (5.0 + 1.4 * product_index) * store_scale * seasonal * trend * promo_lift
                true_demand = int(rng.poisson(max(mean, 0.1)))
                sold_units = min(on_hand, true_demand)
                stockout_flag = int(sold_units < true_demand)
                waste_units = int(rng.binomial(max(on_hand - sold_units, 0), 0.03))
                on_hand = max(0, on_hand - sold_units - waste_units)
                delivery_units = 0
                if day_index % 5 == 0:
                    delivery_units = int(rng.choice([8, 12, 16]))
                    on_hand += delivery_units

                sales_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "store_id": store_id,
                        "product_id": product_id,
                        "sold_units": sold_units,
                        "stockout_flag": stockout_flag,
                        "transaction_count": max(1, sold_units + int(rng.integers(-2, 4))),
                        "known_at": f"{date.date().isoformat()}T23:15:00",
                    }
                )
                truth_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "store_id": store_id,
                        "product_id": product_id,
                        "true_demand": true_demand,
                    }
                )
                inventory_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "store_id": store_id,
                        "product_id": product_id,
                        "observed_inventory": on_hand + int(rng.integers(-2, 3)),
                        "snapshot_time": f"{date.date().isoformat()}T06:00:00",
                    }
                )
                if delivery_units:
                    delivery_rows.append(
                        {
                            "date": date.date().isoformat(),
                            "store_id": store_id,
                            "product_id": product_id,
                            "delivered_units": delivery_units,
                            "ordered_units": delivery_units + int(rng.choice([0, 0, 4])),
                            "received_at": f"{date.date().isoformat()}T05:45:00",
                        }
                    )
                if waste_units:
                    waste_rows.append(
                        {
                            "date": date.date().isoformat(),
                            "store_id": store_id,
                            "product_id": product_id,
                            "waste_units": waste_units,
                            "reason": "expiry",
                        }
                    )
                price_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "store_id": store_id,
                        "product_id": product_id,
                        "price": price,
                        "known_at": f"{date.date().isoformat()}T05:00:00",
                    }
                )
                if planned_promo:
                    promo_rows.append(
                        {
                            "date": date.date().isoformat(),
                            "store_id": store_id,
                            "product_id": product_id,
                            "promotion_flag": 1,
                            "discount": discount,
                            "known_at": f"{date.date().isoformat()}T05:30:00",
                        }
                    )

    sales_frame = pd.DataFrame(sales_rows)
    if not sales_frame.empty:
        sales_frame = pd.concat([sales_frame, sales_frame.iloc[[5]]], ignore_index=True)
        sales_frame.loc[len(sales_frame) - 1, "transaction_count"] = -1

    inventory_frame = pd.DataFrame(inventory_rows)
    if not inventory_frame.empty:
        inventory_frame.loc[0, "observed_inventory"] = -3

    promo_frame = pd.DataFrame(promo_rows)
    if not promo_frame.empty:
        promo_frame.loc[0, "known_at"] = f"{promo_frame.loc[0, 'date']}T10:00:00"

    files = {
        "sales": "sales.csv",
        "inventory": "inventory_snapshots.csv",
        "deliveries": "deliveries.csv",
        "waste": "waste.csv",
        "prices": "prices.csv",
        "promotions": "promotions.csv",
        "products": "products.csv",
        "truth": "evaluator_only/hidden_truth.csv",
        "metadata": "metadata.json",
    }

    _write_csv(sales_frame, output_dir / files["sales"])
    _write_csv(inventory_frame, output_dir / files["inventory"])
    _write_csv(pd.DataFrame(delivery_rows), output_dir / files["deliveries"])
    _write_csv(pd.DataFrame(waste_rows), output_dir / files["waste"])
    _write_csv(pd.DataFrame(price_rows), output_dir / files["prices"])
    _write_csv(promo_frame, output_dir / files["promotions"])
    _write_csv(products_frame, output_dir / files["products"])
    _write_csv(pd.DataFrame(truth_rows), output_dir / files["truth"])
    (output_dir / files["metadata"]).write_text(
        json.dumps({"spec": asdict(effective_spec), "files": files}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {key: str(output_dir / value) for key, value in files.items()}
