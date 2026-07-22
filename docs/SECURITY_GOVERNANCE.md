# Security Governance

This design hardens the project while keeping the data assumptions realistic: the current system uses retailer transactions, store operations, supplier records, staff overrides, and logs. It does not assume unrelated personal-data flows.

## Data Classification

| Asset | Classification | Sensitive rows | Retention | Deletion |
| --- | --- | --- | ---: | --- |
| Transactions | Confidential | No | 730 days | Partition delete |
| Store operations | Internal | No | 365 days | Partition delete |
| Supplier records | Confidential | No | 730 days | Contractual delete |
| Staff overrides | Restricted | Yes | 365 days | Row delete with audit |
| Structured logs | Internal | No row-level values | 180 days | Partition delete |

All confidential and restricted assets require encryption at rest and in transit.

## Access Matrix

| Principal | Environment | Can read data | Can train | Can score | Can approve | Can publish | Can override | Can audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `svc-train-dev` | dev | Yes | Yes | No | No | No | No | No |
| `svc-score-prod` | prod | Yes | No | Yes | No | No | No | No |
| `svc-publish-prod` | prod | No | No | No | No | Yes | No | No |
| `group-policy-review` | prod | No | No | No | Yes | No | No | No |
| `group-store-review` | prod | No | No | No | No | No | Yes | No |
| `group-audit` | prod | No | No | No | No | No | No | Yes |
| `svc-monitor-prod` | prod metrics only | Yes | No | No | No | No | No | Yes |

No shared all-powerful service account is allowed. Approval and publication must be separated.

## Threat Model

| Asset | Actor | Boundary | Attack path | Control |
| --- | --- | --- | --- | --- |
| Model artifact | Malicious insider or bad deploy | Artifact registry to scorer | Replace artifact after validation | Hash manifest, provenance hash, approval ticket, immutable artifact path |
| Source partitions | Upstream system or operator error | Raw data to feature build | Poisoned or late source partition | Partition manifest, freshness checks, point-in-time availability, quarantine |
| Warehouse SQL | Developer or config input | Dynamic identifiers to BigQuery | Identifier injection | Strict identifier validation and fixed parameter paths |
| Service accounts | Operator or compromised workload | Runtime to cloud resources | Over-permissive access | Per-step identities and resource-scoped roles |
| Retailer data | External exposure | Storage and logs | Leaked row-level records | Encryption, redaction, retention, audit logs |
| Policy activation | Reviewer or publisher | Approval to publication | Unauthorised policy activation | Separate approver and publisher, allow-list, rollback pointer |
| Automation changes | Repository workflow | Code review to release | Bypassing review on critical files | Branch protection, required checks, owner review for governance paths |

## Secure Deployment Checklist

- Use Secret Manager and workload identity for runtime secrets.
- Never commit service account keys, private keys, or credential JSON.
- Use separate cloud projects and service accounts for dev, staging, and prod.
- Encrypt storage, warehouse datasets, artifacts, and logs.
- Publish only immutable artifacts with hash manifests.
- Require approval records for model and policy promotion.
- Keep data access, policy approval, publication, store override, and audit roles separate.
- Run dependency, container, and infrastructure scans before release.
- Validate dynamic warehouse identifiers before SQL generation.
- Keep audit logs for data access, overrides, parameter changes, artifact promotion, and publication.

## Dependency And Container Policy

- Pin dependencies through Poetry lockfiles.
- Review dependency updates through CI.
- Build containers from a minimal runtime image.
- Scan the image and Python dependency graph before release.
- Block critical vulnerabilities unless an accepted exception records owner, expiry, and compensating control.

## Artifact Promotion

Promotion requires:

- Artifact id and hash.
- Configuration hash.
- Source partition manifest hash.
- Code revision.
- Approval ticket.
- Approver distinct from publisher.
- Environment-scoped publication identity.

Publication is rejected when the artifact hash does not match the approval record.

## Audit Logs

Audit events must record actor, environment, resource, action, timestamp, and redacted metadata. Logs must not include secrets, tokens, private keys, staff names, customer tokens, or row-level sensitive values.

## Escalation Path

1. Stop publication or revert to the previous valid batch.
2. Page the owner for the affected layer: data, platform, decision, operations, or security.
3. Freeze artifact promotion and policy activation.
4. Preserve audit logs, manifests, active pointer, and approval tickets.
5. Rotate exposed credentials if a secret leak is suspected.
6. Record impact, root cause, corrective actions, and closure evidence.
