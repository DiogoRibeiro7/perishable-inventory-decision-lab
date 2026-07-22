# Workflow Guardrails

This guide defines the repeatable repository workflow for automated coding support and human review.

## Required Sequence

1. Read the work brief and relevant contracts.
2. Audit current files before proposing edits.
3. Name the intended files, public interfaces, risks, and acceptance checks.
4. Build the smallest vertical slice that proves the behavior.
5. Add or update tests before completion.
6. Run `poetry run ruff check .`, `poetry run mypy src`, `poetry run pytest`, and focused validation.
7. Review the diff for unrelated changes.
8. Update docs and traceability when behavior changes.
9. Report exact commands and results.

## Prohibited Changes

- Silent dependency replacement.
- Disabled, skipped, or weakened tests without a documented reason.
- Weakened typing configuration.
- Hard-coded credentials or private key material.
- Fabricated metrics or unsupported commercial impact.
- Business logic that exists outside package code.
- Look-ahead leakage in training or scoring paths.
- Unsupported production readiness claims.

## Approval Required

Ask for explicit approval before changing:

- database schemas or warehouse table contracts;
- public Python interfaces;
- cloud resources, IAM, publication, or rollback behavior;
- large modelling dependencies;
- default runtime behavior for scoring or publication.

## Evidence Standard

A reviewer should be able to reproduce the claimed result from committed files and command output. If a check was not run, state why and name the residual risk.
