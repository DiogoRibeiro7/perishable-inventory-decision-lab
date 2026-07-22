# Repository Automation Guide

This repository accepts changes from automated coding helpers only when the work is scoped, reproducible, and reviewable from committed evidence.

## Required Work Cycle

1. Read the relevant work brief and repository contracts.
2. Inspect the current implementation before editing.
3. State the intended files, public interfaces, risks, and acceptance checks.
4. Implement the smallest coherent vertical slice.
5. Add or update tests before reporting completion.
6. Run formatting, linting, typing, tests, and focused validation.
7. Inspect the diff for unrelated changes.
8. Update documentation and traceability when behavior or interfaces change.
9. Report commands and actual results.

## Change Boundaries

Do not silently replace dependencies, weaken type checks, disable tests, commit credentials, fabricate metrics, hide required logic in notebooks, use future information in training features, or make unsupported production claims.

Require explicit human approval before:

- schema migrations;
- public API changes;
- new cloud resources;
- large modelling dependencies;
- changes to access control, publication, or rollback behavior.

## Evidence Rules

Every completion report should let another reviewer reproduce the work from the repository alone. Include the diff scope, commands run, results, unresolved risks, and any follow-up items.

Templates and checklists live in:

- `docs/WORKFLOW_GUARDRAILS.md`
- `docs/TASK_TEMPLATE.md`
- `docs/COMPLETION_REPORT_TEMPLATE.md`
- `docs/INPUT_SELECTION_TREE.md`
- `docs/CHANGE_REVIEW_CHECKLIST.md`
