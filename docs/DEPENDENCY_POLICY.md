# Dependency Policy

The dependency and container policy is part of the release gate.

Required checks:

- Python dependency resolution through Poetry.
- Ruff and mypy.
- Full pytest suite.
- Container build.
- Dependency vulnerability scan.
- Container vulnerability scan.
- Infrastructure configuration scan for public storage, broad roles, and missing encryption.

Exception policy:

- Critical findings block release unless an exception has an owner, expiry date, impacted component, compensating control, and approval ticket.
- High findings require remediation plan before production rollout.
- Medium and low findings are triaged in the delivery backlog.

Secrets policy:

- Runtime secrets come from Secret Manager through workload identity.
- Committed service-account keys and private keys are prohibited.
- Logs are redacted before emission.
