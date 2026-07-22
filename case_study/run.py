"""One-command runner for the take-home case study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from case_study.evaluator import evaluate_outputs
from case_study.generator import CaseStudySpec, generate_case_study_data
from case_study.reference_solution import run_reference_solution


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and solve the take-home case study.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/take_home_case_study"))
    parser.add_argument("--seed", type=int, default=1307)
    args = parser.parse_args()

    data_dir = args.output / "data"
    solution_dir = args.output / "reference_solution"
    generate_case_study_data(data_dir, CaseStudySpec(seed=args.seed))
    run_reference_solution(data_dir, solution_dir)
    result = evaluate_outputs(data_dir, solution_dir)
    print(json.dumps({"score": result.score, "checks": result.checks}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
