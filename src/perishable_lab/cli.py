"""Command-line interface for the showcase project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from perishable_lab.analysis import ProfileConfig, write_profile_report
from perishable_lab.config import load_config
from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.pipelines.demo import run_demo

app = typer.Typer(
    name="perishable-lab",
    help="Probabilistic forecasting and perishable inventory decision laboratory.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run reproducible forecasting and inventory workflows."""


@app.command()
def demo(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory in which generated artifacts are written."),
    ] = Path("artifacts/demo"),
    config_path: Annotated[
        Path,
        typer.Option(help="Validated YAML configuration file."),
    ] = Path("configs/base.yaml"),
    days: Annotated[int | None, typer.Option(min=60)] = None,
    stores: Annotated[int | None, typer.Option(min=1)] = None,
    products: Annotated[int | None, typer.Option(min=1)] = None,
    seed: Annotated[int | None, typer.Option()] = None,
    service_level: Annotated[
        float | None,
        typer.Option(min=0.51, max=0.99),
    ] = None,
) -> None:
    """Generate data, train forecasts, and evaluate inventory policies."""
    config = load_config(config_path)
    updates: dict[str, object] = {}
    if days is not None:
        updates["days"] = days
    if stores is not None:
        updates["stores"] = stores
    if products is not None:
        updates["products"] = products
    if seed is not None:
        updates["seed"] = seed
    if updates:
        config.simulation = config.simulation.model_copy(update=updates)
    if service_level is not None:
        config.inventory = config.inventory.model_copy(
            update={"service_level": service_level}
        )

    result = run_demo(config, output_dir)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("profile-data")
def profile_data(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory in which profile artifacts are written."),
    ] = Path("artifacts/profile"),
    input_path: Annotated[
        Path | None,
        typer.Option(help="Optional CSV file containing store-product-day data."),
    ] = None,
    config_path: Annotated[
        Path,
        typer.Option(help="Validated YAML configuration file used when no input CSV is provided."),
    ] = Path("configs/base.yaml"),
    min_segment_size: Annotated[int, typer.Option(min=1)] = 20,
) -> None:
    """Profile store-product-day data and write deterministic quality reports."""
    if input_path is None:
        app_config = load_config(config_path)
        frame = generate_daily_demand(
            SyntheticDataSpec(
                days=app_config.simulation.days,
                stores=app_config.simulation.stores,
                products=app_config.simulation.products,
                seed=app_config.simulation.seed,
            )
        )
        source_table = "synthetic_daily_demand"
    else:
        frame = pd.read_csv(input_path)
        source_table = input_path.stem

    result = write_profile_report(
        frame,
        output_dir,
        source_table=source_table,
        config=ProfileConfig(min_segment_size=min_segment_size),
    )
    typer.echo(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "rows": int(frame.shape[0]),
                "quality_issues": len(result.quality_issues),
                "blocking_issues": sum(1 for issue in result.quality_issues if issue.severity == "blocking"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
