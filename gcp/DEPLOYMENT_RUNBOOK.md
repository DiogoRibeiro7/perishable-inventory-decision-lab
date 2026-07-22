# Deployment Runbook

## Release flow

1. Run `make quality` locally.
2. Build and push an immutable image tagged with the Git commit SHA.
3. Run dbt source and staging checks before scoring.
4. Execute scoring for one business-date partition with a deterministic execution ID.
5. Publish recommendations with a delete-and-insert transaction for that partition.
6. Validate row counts, non-negative recommendations, model version, policy version, and generation timestamp.
7. Promote the batch only after monitoring checks are healthy or explicitly approved.

## Operational safeguards

- Use workload identity and separate service accounts for transformation, scoring, and monitoring jobs.
- Scope BigQuery permissions to the exact datasets each workload reads or writes.
- Keep Cloud Run Jobs retry-safe by making every write partition-scoped and idempotent.
- Store model packages, calibration objects, reports, and run manifests in immutable object paths.
- Roll back by republishing the previous model and policy versions for the affected business-date partitions.

## Compute choice

Cloud Run Jobs are the default for this project because scoring and simulation are batch-oriented, container-native, and small enough to run without managed training infrastructure. Managed custom jobs remain a better fit when training requires accelerators, distributed workers, or long-running experiments with richer experiment tracking.
