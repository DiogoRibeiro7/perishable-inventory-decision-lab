# Change Review Checklist

## Scope

- The diff is limited to the stated files.
- No unrelated formatting or generated artifact churn is included.
- New public interfaces are documented.
- Schema or cloud changes have explicit approval evidence.

## Correctness

- Tests cover the changed behavior.
- Edge cases include missing data, duplicates, stale inputs, and invalid quantities where relevant.
- Forecast features are available at cutoff.
- Inventory logic preserves non-negative quantities and conservation.

## Quality

- Ruff, mypy, and pytest pass.
- Type settings are not weakened.
- Tests are not skipped or disabled without a documented reason.
- Dependencies are not replaced silently.

## Safety

- No credentials, private keys, or local secrets are committed.
- No fabricated metrics or unsupported production claims are introduced.
- Notebook code is not the only executable implementation.
- Rollback and publication behavior remain explicit.

## Examples

Good change: adds a small adapter behind an existing interface, tests conversion and missing-file behavior, updates docs, runs the full quality gate, and reports residual limitations.

Rejected change: swaps a modelling library, lowers type strictness, skips failing tests, commits a large raw dataset, and claims operational improvement without linked evidence.
