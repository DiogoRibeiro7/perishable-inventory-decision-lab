"""Command-line interface for the showcase project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from perishable_lab.config import load_config
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


if __name__ == "__main__":
    app()
