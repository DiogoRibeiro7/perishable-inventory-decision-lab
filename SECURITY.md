# Security Policy

## Supported Versions

The current supported release line is:

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a Vulnerability

Please do not open a public issue for security-sensitive concerns.

Report vulnerabilities by email: dfr@esmad.ipp.pt.

Include:

- Affected version or commit.
- Reproduction steps or proof of impact.
- Any relevant logs, configuration, or file paths.
- Whether credentials, private data, or publication paths may be exposed.

## Response

Reports will be reviewed for severity, reproducibility, and affected surface. When a fix is needed, the expected path is:

1. Confirm receipt.
2. Reproduce and scope the issue.
3. Prepare a fix and regression test.
4. Publish the fix with a clear release note when appropriate.

## Security Expectations

- Do not commit credentials or private datasets.
- Keep generated artifacts out of version control unless they are compact release evidence.
- Validate recommendation batches before publication.
- Keep dependency updates reviewable through CI and Dependabot.
