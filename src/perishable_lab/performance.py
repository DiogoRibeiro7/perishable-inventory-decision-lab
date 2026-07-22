"""Benchmark workloads, profiling, and deterministic scaling helpers."""

from __future__ import annotations

import json
import time
import tracemalloc
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypeVar

import numpy as np
import pandas as pd

from perishable_lab.data.synthetic import SyntheticDataSpec, generate_daily_demand
from perishable_lab.features import build_features

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class WorkloadSpec:
    """Representative benchmark workload."""

    name: str
    stores: int
    products: int
    days: int
    horizons: int
    quantiles: int
    scenarios: int
    policy_candidates: int
    sparse: bool = False
    promotion_heavy: bool = False
    seed: int = 42

    @property
    def expected_rows(self) -> int:
        """Return panel row count before lag trimming."""
        return self.stores * self.products * self.days

    @property
    def expected_series(self) -> int:
        """Return store-product series count."""
        return self.stores * self.products


@dataclass(frozen=True)
class BenchmarkMetric:
    """Measured benchmark metric for one step."""

    step: str
    wall_time_seconds: float
    cpu_time_seconds: float
    peak_memory_mb: float
    input_rows: int
    output_rows: int
    rows_per_second: float
    series_per_second: float
    estimated_cloud_cost_usd: float


@dataclass(frozen=True)
class PerformanceBudget:
    """Regression budget for small benchmark checks."""

    max_wall_time_seconds: float
    max_peak_memory_mb: float
    max_estimated_cloud_cost_usd: float


@dataclass(frozen=True)
class ChunkedResult:
    """Result and observed peak memory for chunked scoring."""

    frame: pd.DataFrame
    peak_memory_mb: float


def default_workloads() -> tuple[WorkloadSpec, ...]:
    """Return small, medium, large, sparse, and promotion-heavy benchmark workloads."""
    return (
        WorkloadSpec("small", stores=2, products=4, days=80, horizons=7, quantiles=5, scenarios=100, policy_candidates=3),
        WorkloadSpec("medium", stores=10, products=40, days=240, horizons=14, quantiles=7, scenarios=500, policy_candidates=5),
        WorkloadSpec("large", stores=80, products=250, days=540, horizons=28, quantiles=9, scenarios=1000, policy_candidates=7),
        WorkloadSpec("sparse", stores=8, products=30, days=240, horizons=14, quantiles=7, scenarios=500, policy_candidates=5, sparse=True),
        WorkloadSpec(
            "promotion_heavy",
            stores=8,
            products=30,
            days=240,
            horizons=14,
            quantiles=7,
            scenarios=500,
            policy_candidates=5,
            promotion_heavy=True,
        ),
    )


def generate_benchmark_dataset(spec: WorkloadSpec) -> pd.DataFrame:
    """Generate a representative benchmark dataset for a workload."""
    frame = generate_daily_demand(
        SyntheticDataSpec(days=spec.days, stores=spec.stores, products=spec.products, seed=spec.seed)
    )
    rng = np.random.default_rng(spec.seed + 17)
    if spec.sparse:
        sparse_mask = rng.random(frame.shape[0]) < 0.35
        frame.loc[sparse_mask, "demand"] = 0
    if spec.promotion_heavy:
        promotion_mask = rng.random(frame.shape[0]) < 0.40
        frame.loc[promotion_mask, "promotion"] = 1
    return frame


def profile_step(
    step: str,
    fn: Callable[[], pd.DataFrame],
    *,
    input_rows: int,
    series: int,
) -> tuple[pd.DataFrame, BenchmarkMetric]:
    """Measure wall time, CPU time, peak memory, throughput, and cost estimate."""
    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    result = fn()
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_memory_mb = peak_bytes / (1024.0 * 1024.0)
    output_rows = int(result.shape[0])
    rows_per_second = output_rows / wall_seconds if wall_seconds > 0 else float("inf")
    metric = BenchmarkMetric(
        step=step,
        wall_time_seconds=wall_seconds,
        cpu_time_seconds=cpu_seconds,
        peak_memory_mb=peak_memory_mb,
        input_rows=input_rows,
        output_rows=output_rows,
        rows_per_second=rows_per_second,
        series_per_second=series / wall_seconds if wall_seconds > 0 else float("inf"),
        estimated_cloud_cost_usd=estimate_cloud_cost(cpu_seconds=cpu_seconds, peak_memory_mb=peak_memory_mb),
    )
    return result, metric


def estimate_cloud_cost(*, cpu_seconds: float, peak_memory_mb: float, bigquery_bytes: int = 0) -> float:
    """Return a simple Cloud Run plus BigQuery cost estimate."""
    vcpu_second_cost = 0.000024
    gib_second_cost = 0.0000025
    bigquery_tib_cost = 6.25
    memory_gib_seconds = (peak_memory_mb / 1024.0) * cpu_seconds
    bigquery_tib = bigquery_bytes / float(1024**4)
    return (cpu_seconds * vcpu_second_cost) + (memory_gib_seconds * gib_second_cost) + (bigquery_tib * bigquery_tib_cost)


def reference_panel_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Readable reference implementation for panel summary metrics."""
    rows: list[dict[str, object]] = []
    for (store_id, product_id), group in frame.groupby(["store_id", "product_id"], sort=True):
        rows.append(
            {
                "store_id": store_id,
                "product_id": product_id,
                "demand_sum": float(group["demand"].sum()),
                "demand_mean": float(group["demand"].mean()),
                "promotion_rate": float(group["promotion"].mean()),
            }
        )
    return pd.DataFrame(rows)


def optimized_panel_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Vectorised implementation kept in parity with the reference version."""
    return (
        frame.groupby(["store_id", "product_id"], as_index=False, sort=True)
        .agg(
            demand_sum=("demand", "sum"),
            demand_mean=("demand", "mean"),
            promotion_rate=("promotion", "mean"),
        )
        .astype({"demand_sum": "float64", "demand_mean": "float64", "promotion_rate": "float64"})
    )


def deterministic_parallel_map(items: Iterable[T], fn: Callable[[T], U], *, worker_count: int) -> tuple[U, ...]:
    """Map independent work while preserving input order and one-worker behavior."""
    ordered_items = tuple(items)
    if worker_count <= 1:
        return tuple(fn(item) for item in ordered_items)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return tuple(executor.map(fn, ordered_items))


def chunked_score(
    frame: pd.DataFrame,
    score_fn: Callable[[pd.DataFrame], pd.DataFrame],
    *,
    chunk_size: int,
) -> ChunkedResult:
    """Score a frame in bounded chunks without dropping rows."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    tracemalloc.start()
    chunks: list[pd.DataFrame] = []
    for start in range(0, frame.shape[0], chunk_size):
        chunk = frame.iloc[start : start + chunk_size].copy(deep=True)
        chunks.append(score_fn(chunk))
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    scored = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    return ChunkedResult(scored, peak_bytes / (1024.0 * 1024.0))


def partition_frame(frame: pd.DataFrame, *, partition_columns: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Split a frame by partition columns with deterministic keys."""
    missing = sorted(set(partition_columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing partition columns: {missing}")
    partitions: dict[str, pd.DataFrame] = {}
    for keys, group in frame.groupby(list(partition_columns), sort=True, dropna=False):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        partition_key = "|".join(str(value) for value in key_tuple)
        partitions[partition_key] = group.copy(deep=True).reset_index(drop=True)
    return partitions


def combine_partitions(partitions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine partitions without row loss."""
    if not partitions:
        return pd.DataFrame()
    return pd.concat([partitions[key] for key in sorted(partitions)], ignore_index=True)


def run_benchmark(spec: WorkloadSpec) -> dict[str, object]:
    """Run the local benchmark steps and return profiler metrics."""
    metrics: list[BenchmarkMetric] = []
    raw, metric = profile_step(
        "data_ingestion",
        lambda: generate_benchmark_dataset(spec),
        input_rows=spec.expected_rows,
        series=spec.expected_series,
    )
    metrics.append(metric)
    featured, metric = profile_step(
        "feature_generation",
        lambda: build_features(raw),
        input_rows=int(raw.shape[0]),
        series=spec.expected_series,
    )
    metrics.append(metric)
    summary, metric = profile_step(
        "panel_summary",
        lambda: optimized_panel_summary(featured),
        input_rows=int(featured.shape[0]),
        series=spec.expected_series,
    )
    metrics.append(metric)
    _, metric = profile_step(
        "serialization",
        lambda: pd.DataFrame({"payload": [summary.to_json(orient="records")]}),
        input_rows=int(summary.shape[0]),
        series=spec.expected_series,
    )
    metrics.append(metric)
    return {
        "workload": asdict(spec),
        "metrics": [asdict(item) for item in metrics],
        "dominant_bottleneck": max(metrics, key=lambda item: item.wall_time_seconds).step,
    }


def assert_budget(report: dict[str, object], budget: PerformanceBudget) -> None:
    """Raise when a benchmark report exceeds configured budget."""
    raw_metrics = report.get("metrics")
    if not isinstance(raw_metrics, list):
        raise TypeError("Benchmark report metrics must be a list")
    metrics: list[BenchmarkMetric] = []
    for item in raw_metrics:
        if not isinstance(item, dict):
            raise TypeError("Benchmark metric entries must be mappings")
        metrics.append(
            BenchmarkMetric(
                step=str(item["step"]),
                wall_time_seconds=float(item["wall_time_seconds"]),
                cpu_time_seconds=float(item["cpu_time_seconds"]),
                peak_memory_mb=float(item["peak_memory_mb"]),
                input_rows=int(item["input_rows"]),
                output_rows=int(item["output_rows"]),
                rows_per_second=float(item["rows_per_second"]),
                series_per_second=float(item["series_per_second"]),
                estimated_cloud_cost_usd=float(item["estimated_cloud_cost_usd"]),
            )
        )
    wall_time = sum(metric.wall_time_seconds for metric in metrics)
    peak_memory = max(metric.peak_memory_mb for metric in metrics)
    estimated_cost = sum(metric.estimated_cloud_cost_usd for metric in metrics)
    failures: list[str] = []
    if wall_time > budget.max_wall_time_seconds:
        failures.append("wall_time")
    if peak_memory > budget.max_peak_memory_mb:
        failures.append("peak_memory")
    if estimated_cost > budget.max_estimated_cloud_cost_usd:
        failures.append("estimated_cloud_cost")
    if failures:
        raise AssertionError(f"Performance budget exceeded: {failures}")


def write_benchmark_report(report: dict[str, object], output_dir: Path) -> Path:
    """Persist benchmark profiler output as stable JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benchmark_report.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path
