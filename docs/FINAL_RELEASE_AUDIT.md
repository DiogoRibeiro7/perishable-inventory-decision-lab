# Final Release Audit

Version: `0.2.0`

This release package is intended for a reproducible portfolio review of a perishable inventory decision system. It is not a live retailer deployment and does not claim field impact from synthetic evidence.

## Gates

| Area | Evidence | Status |
|---|---|---|
| Install path | `poetry install` on Python 3.11 or 3.12 | Pass |
| Local demo | `poetry run perishable-lab demo --days 90 --stores 2 --products 4 --seed 42 --output-dir artifacts/release-demo-check` | Pass |
| Quality | `poetry run ruff check .` | Pass |
| Types | `poetry run mypy src` | Pass |
| Tests | `poetry run pytest` | Pass |
| Hygiene | `poetry run python scripts/repo_hygiene.py` | Pass |
| Release gate | `poetry run python scripts/release_gate.py --write reports/release/v0.2.0_gate.json` | Pass |

## Verified scope

- README claims link to runnable package code, committed example outputs, or explicit limitations.
- The committed example run remains deterministic and small enough for review.
- Generated data stays outside version control; only compact example metrics and figures are committed.
- Synthetic limitations are documented in the README, example report, model card, policy card, and simulator card.
- Docker, CI, dbt, Airflow, and GCP examples describe one coherent batch pattern.
- Local Markdown links resolve.
- Cards match package version `0.2.0`.
- No raw datasets, credentials, cache folders, or temporary run folders are tracked.

## Adversarial gate

High-risk findings were reviewed before tagging:

| Finding | Decision |
|---|---|
| Synthetic data cannot prove retailer economics. | Documented as a limitation; not blocking for portfolio release. |
| Cloud resources are examples unless configured by the reviewer. | Documented in the runbook; local demo is the reproducible path. |
| Public benchmark adapter needs user-provided M5 files. | Documented as optional external input. |
| Stockout-censored demand handling is included but needs retailer validation. | Covered by canonical, feature, forecasting, demo, and strategy tests; listed as a deployment risk. |
| Segmented calibration needs real operating data. | Documented as follow-up work. |

No blocker remains for an annotated portfolio tag. A field deployment would require retailer data access, stakeholder cost sign-off, and operational validation.
