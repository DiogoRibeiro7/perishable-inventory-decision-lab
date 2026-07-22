"""Command-line interface for the showcase project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
import yaml

from perishable_lab.analysis import ProfileConfig, write_profile_report
from perishable_lab.config import load_config
from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.failures import DiagnosticMode, write_failure_analysis
from perishable_lab.feature_store import (
    FeatureMetadata,
    FeatureRegistry,
    source_partition_manifest,
    write_training_snapshot_manifest,
)
from perishable_lab.performance import (
    PerformanceBudget,
    assert_budget,
    default_workloads,
    run_benchmark,
    write_benchmark_report,
)
from perishable_lab.pipelines.demo import run_demo
from perishable_lab.publication import (
    BatchRequest,
    LocalRecommendationStore,
    ValidationConfig,
    validate_recommendation_batch,
)

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


@app.command("diagnose-failures")
def diagnose_failures_command(
    input_path: Annotated[
        Path,
        typer.Argument(help="CSV file containing forecasts, recommendations, outcomes, and context signals."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory in which failure diagnostics are written."),
    ] = Path("artifacts/failure-analysis"),
    mode: Annotated[
        str,
        typer.Option(help="Diagnostic mode: real_time or post_outcome."),
    ] = "post_outcome",
) -> None:
    """Write row-level failures, episodes, and a ranked diagnostic report."""
    if mode not in {"real_time", "post_outcome"}:
        raise typer.BadParameter("mode must be real_time or post_outcome")
    checked_mode: DiagnosticMode = "real_time" if mode == "real_time" else "post_outcome"
    frame = pd.read_csv(input_path)
    outputs = write_failure_analysis(frame, output_dir, mode=checked_mode)
    typer.echo(json.dumps(outputs, indent=2, sort_keys=True))


@app.command("snapshot-features")
def snapshot_features(
    input_path: Annotated[
        Path,
        typer.Argument(help="CSV file containing a frozen training feature table."),
    ],
    output_path: Annotated[
        Path,
        typer.Option(help="JSON manifest path to write."),
    ] = Path("artifacts/feature-store/training_snapshot_manifest.json"),
    partition_columns: Annotated[
        str,
        typer.Option(help="Comma-separated source partition columns present in the input CSV."),
    ] = "date",
) -> None:
    """Write a reproducible training feature snapshot manifest."""
    frame = pd.read_csv(input_path)
    partitions = tuple(column.strip() for column in partition_columns.split(",") if column.strip())
    registry = FeatureRegistry(
        tuple(
            FeatureMetadata(
                name=column,
                owner="local",
                source=input_path.stem,
                transformation="snapshot_input",
                unit="source_unit",
                availability_delay_hours=0.0,
                freshness_sla_hours=24.0,
                null_policy="allow",
                version="snapshot-v1",
                dtype=str(frame[column].dtype),
            )
            for column in sorted(frame.columns)
        )
    )
    manifest = write_training_snapshot_manifest(
        frame,
        registry,
        source_partition_manifest({input_path.stem: frame}, partition_columns=partitions),
        output_path,
    )
    typer.echo(json.dumps(manifest, indent=2, sort_keys=True))


@app.command("publish-recommendations")
def publish_recommendations(
    input_path: Annotated[
        Path,
        typer.Argument(help="CSV file containing a complete recommendation batch."),
    ],
    store_path: Annotated[
        Path,
        typer.Option(help="Local publication store directory."),
    ] = Path("artifacts/publication"),
    retailer_id: Annotated[str, typer.Option()] = "demo-retailer",
    business_date: Annotated[str, typer.Option()] = "2026-01-01",
    config_hash: Annotated[str, typer.Option()] = "local-config",
    data_version: Annotated[str, typer.Option()] = "local-data",
    model_version: Annotated[str, typer.Option()] = "model-v1",
    policy_version: Annotated[str, typer.Option()] = "policy-v1",
    expected_rows: Annotated[int, typer.Option(min=1)] = 1,
    expected_unit: Annotated[str, typer.Option()] = "unit",
    now: Annotated[str, typer.Option()] = "2026-01-01T12:00:00Z",
) -> None:
    """Validate, stage, and atomically publish a local recommendation batch."""
    frame = pd.read_csv(input_path)
    request = BatchRequest(
        retailer_id=retailer_id,
        business_date=business_date,
        config_hash=config_hash,
        data_version=data_version,
        model_version=model_version,
        policy_version=policy_version,
    )
    report = validate_recommendation_batch(
        frame,
        request,
        ValidationConfig(expected_rows=expected_rows, expected_unit=expected_unit, now=now),
    )
    if report.status != "pass":
        typer.echo(json.dumps({"status": "fail", "issues": [issue.__dict__ for issue in report.issues]}, indent=2))
        raise typer.Exit(1)
    store = LocalRecommendationStore(store_path)
    manifest = store.stage_batch(frame, request, report)
    pointer = store.publish_batch(manifest.batch_id)
    typer.echo(json.dumps({"status": "published", "batch_id": pointer.active_batch_id, "generation": pointer.generation}, indent=2))


@app.command("rollback-recommendations")
def rollback_recommendations(
    store_path: Annotated[
        Path,
        typer.Option(help="Local publication store directory."),
    ] = Path("artifacts/publication"),
) -> None:
    """Roll back local recommendations to the previous valid batch."""
    pointer = LocalRecommendationStore(store_path).rollback()
    typer.echo(json.dumps({"status": "rolled_back", "batch_id": pointer.active_batch_id, "generation": pointer.generation}, indent=2))


@app.command("benchmark")
def benchmark(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory in which benchmark reports are written."),
    ] = Path("artifacts/benchmark"),
    workload: Annotated[
        str,
        typer.Option(help="Workload name from small, medium, large, sparse, promotion_heavy."),
    ] = "small",
    budget_path: Annotated[
        Path | None,
        typer.Option(help="Optional YAML file with benchmark regression thresholds."),
    ] = Path("configs/performance_budget.example.yaml"),
    fail_on_budget: Annotated[
        bool,
        typer.Option(help="Exit with failure when the benchmark exceeds the configured budget."),
    ] = False,
) -> None:
    """Run a local benchmark workload and write a profiler report."""
    workloads = {spec.name: spec for spec in default_workloads()}
    if workload not in workloads:
        raise typer.BadParameter(f"Unknown workload: {workload}")
    report = run_benchmark(workloads[workload])
    report_path = write_benchmark_report(report, output_dir)
    if fail_on_budget and budget_path is not None:
        budget_payload = yaml.safe_load(budget_path.read_text(encoding="utf-8"))
        assert_budget(report, PerformanceBudget(**budget_payload[workload]))
    typer.echo(json.dumps({"output_path": str(report_path), "dominant_bottleneck": report["dominant_bottleneck"]}, indent=2))


if __name__ == "__main__":
    app()
