# Contributing

Thanks for considering a contribution. This repository is a reproducible software project for probabilistic forecasting, perishable inventory simulation, and replenishment policy evaluation.

## Ground Rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep changes scoped and reviewable.
- Do not commit credentials, private datasets, generated run folders, caches, or local environment files.
- Do not make retailer outcome claims unless they are backed by linked evidence.
- Prefer small pull requests with tests and documentation where behavior changes.

## Local Setup

Requirements: Python 3.11 or 3.12 and Poetry.

```bash
poetry install
poetry run perishable-lab demo --output-dir artifacts/demo
```

Generated outputs belong under `artifacts/` and should stay outside version control.

## Quality Checks

Run these before opening a pull request:

```bash
poetry run ruff check .
poetry run mypy src
poetry run pytest
poetry run python scripts/repo_hygiene.py
```

For release-facing changes, also run:

```bash
poetry run python scripts/release_gate.py --write reports/release/v0.1.0_gate.json
```

Only commit the generated release report when the change intentionally updates release evidence.

## Pull Request Scope

Include:

- What changed.
- Why it changed.
- Commands run and their results.
- Any limitations, risks, or follow-up work.

Avoid mixing unrelated refactors with behavior changes.

## Documentation

Update README, cards, reports, or docs when changing:

- Source contracts or feature timing.
- Forecast targets, metrics, or calibration.
- Inventory simulator behavior.
- Ordering policy logic.
- Publication, monitoring, rollback, security, or release evidence.
