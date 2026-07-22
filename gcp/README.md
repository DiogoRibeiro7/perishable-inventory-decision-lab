# GCP Deployment Pattern

The core demo is local and cloud-agnostic. A production implementation can use:

- **BigQuery** for validated features, forecasts, recommendations, and realised outcomes.
- **dbt or Dataform** for source contracts and incremental transformations.
- **Cloud Run Jobs** for scheduled training, scoring, simulation, and monitoring workloads.
- **Model registry or object storage** for model lineage and staged promotion.
- **Cloud Storage** for immutable model packages, calibration objects, and reports.
- **Cloud Composer** for orchestration.
- **Cloud Monitoring** for job failures and custom operational metrics.

The supplied Cloud Build file tests the package, builds the container, pushes it to Artifact Registry, and deploys a Cloud Run Job. Production credentials should use workload identity and least-privilege service accounts; no long-lived service-account key should be committed.
