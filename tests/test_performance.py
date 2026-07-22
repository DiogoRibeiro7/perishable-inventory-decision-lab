from __future__ import annotations

import pandas as pd
import pytest

from perishable_lab.performance import (
    PerformanceBudget,
    assert_budget,
    chunked_score,
    combine_partitions,
    default_workloads,
    deterministic_parallel_map,
    generate_benchmark_dataset,
    optimized_panel_summary,
    partition_frame,
    reference_panel_summary,
    run_benchmark,
)

pytestmark = pytest.mark.extended


def test_optimized_summary_matches_reference_output() -> None:
    frame = generate_benchmark_dataset(default_workloads()[0])

    reference = reference_panel_summary(frame)
    optimized = optimized_panel_summary(frame)

    pd.testing.assert_frame_equal(reference, optimized)


def test_parallel_map_is_deterministic_and_one_worker_matches() -> None:
    def square(value: int) -> int:
        return value * value

    one_worker = deterministic_parallel_map(range(10), square, worker_count=1)
    four_workers = deterministic_parallel_map(range(10), square, worker_count=4)

    assert one_worker == four_workers


def test_chunked_scoring_preserves_rows_and_bounds_peak_memory() -> None:
    frame = pd.DataFrame({"x": range(100)})

    def score(chunk: pd.DataFrame) -> pd.DataFrame:
        scored = chunk.copy(deep=True)
        scored["score"] = scored["x"] + 1
        return scored

    result = chunked_score(frame, score, chunk_size=13)

    assert result.frame.shape[0] == frame.shape[0]
    assert result.frame["score"].iloc[-1] == 100
    assert result.peak_memory_mb < 10


def test_partition_roundtrip_has_no_data_loss() -> None:
    frame = pd.DataFrame({"store_id": ["s1", "s1", "s2"], "value": [1, 2, 3]})

    partitions = partition_frame(frame, partition_columns=("store_id",))
    combined = combine_partitions(partitions).sort_values(["store_id", "value"], ignore_index=True)

    pd.testing.assert_frame_equal(combined, frame)


def test_small_benchmark_has_required_steps_and_budget_check() -> None:
    report = run_benchmark(default_workloads()[0])
    steps = [metric["step"] for metric in report["metrics"]]

    assert steps == ["data_ingestion", "feature_generation", "panel_summary", "serialization"]
    assert report["dominant_bottleneck"] in steps
    assert_budget(
        report,
        PerformanceBudget(
            max_wall_time_seconds=60.0,
            max_peak_memory_mb=512.0,
            max_estimated_cloud_cost_usd=1.0,
        ),
    )


def test_budget_failure_is_explicit() -> None:
    report = run_benchmark(default_workloads()[0])

    with pytest.raises(AssertionError, match="Performance budget exceeded"):
        assert_budget(
            report,
            PerformanceBudget(
                max_wall_time_seconds=0.0,
                max_peak_memory_mb=0.0,
                max_estimated_cloud_cost_usd=0.0,
            ),
        )
