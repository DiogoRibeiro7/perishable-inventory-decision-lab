# High: Enforce Service Floors During Policy Selection

## Problem

A lower-cost policy can be favored even when it violates required availability for a priority segment.

## Evidence

- `src/perishable_lab/evaluation/reporting.py`
- `reports/example_results.md`
- `tests/test_monitoring.py`

## Required Work

- Rank policies by cost only after applying global and segment fill-rate floors.
- Add rejection reasons for infeasible policies.
- Add selected-policy status to report artifacts.

## Acceptance Criteria

- A cheaper policy that violates fill-rate constraints is rejected in tests.
- Reports list feasible, rejected, and selected policies.
- Existing policy metrics remain backward compatible.
