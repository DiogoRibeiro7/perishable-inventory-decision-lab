# System Card

## Scope

Card version: `system-card-v1`

Package version: `0.1.0`

Owner: platform

## Architecture

The system is batch-first:

1. Source contracts validate store-product-day data.
2. Feature generation applies point-in-time rules.
3. Forecasting produces versioned distributions.
4. Decision contracts validate inventory, pending orders, units, horizon, and policy inputs.
5. Simulation and offline checks evaluate candidate policies.
6. Publication stages immutable batches and atomically swaps the active pointer.
7. Monitoring checks data, model, decision, and system health.

Evidence: `docs/ARCHITECTURE.md`, `docs/FEATURE_STORE_LINEAGE.md`, `docs/PUBLICATION_RUNBOOK.md`, `tests/test_publication.py`.

## Data Lineage And Batch Timing

Feature sets persist source partition manifests, feature-set hashes, transformation versions, and availability timestamps. Batch publication is allowed only after validation passes.

## Monitoring And Rollback

Monitoring covers freshness, completeness, duplicate records, artifact integrity, coverage, order jumps, partition completeness, publication state, and rollback readiness. Incident controls are documented in `docs/OBSERVABILITY_RUNBOOK.md` and tested in `tests/test_observability.py`.

## Human Roles

- Forecasting owner maintains model evidence.
- Decision owner maintains policy evidence.
- Operations reviewers capture overrides and reasons.
- Policy reviewers approve production changes.
- Publication service publishes only approved artifacts.
- Audit reviewers inspect data access, overrides, parameter changes, and publication.

## Security And Boundaries

Production roles are least-privilege and separated. Environment-scoped resources prevent dev, staging, and production crossover. Security controls are documented in `docs/SECURITY_GOVERNANCE.md` and tested in `tests/test_security.py`.

## Stop Or Override

An operator can hold publication, revert to the previous valid batch, activate the safe incumbent policy, or record a human override. Store-facing readers never consume a partial staged batch.
