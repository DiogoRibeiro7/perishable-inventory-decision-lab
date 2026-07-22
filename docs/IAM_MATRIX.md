# IAM Matrix

| Role | Principal | Resources | Allowed actions | Explicitly denied |
| --- | --- | --- | --- | --- |
| Training service | `svc-train-dev` | `dev.features.*` | Read data, train models | Prod data, publication, approval |
| Scoring service | `svc-score-prod` | `prod.features.*`, `prod.models.approved` | Read data, score batches | Training writes, approval, publication |
| Publication service | `svc-publish-prod` | `prod.publication.*` | Publish approved batches | Read raw data, approve policies, override orders |
| Policy reviewers | `group-policy-review` | `prod.policies.pending` | Approve policy promotion | Publish recommendations |
| Store reviewers | `group-store-review` | `prod.store_orders.*` | Override orders with reason capture | Approve policy, publish batches |
| Audit reviewers | `group-audit` | `prod.audit.*` | Audit changes | Modify data, approve policy, publish |
| Monitoring service | `svc-monitor-prod` | `prod.metrics.*` | Read metrics, write monitoring records | Raw-data export, publication |

Each production role is intentionally narrow. No production principal can both approve and publish recommendations.
