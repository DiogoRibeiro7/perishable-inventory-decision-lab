# Input Selection Tree

Use this tree to decide how to translate a work brief into repository changes.

1. If the brief changes data grain, schemas, or source contracts, start with `src/perishable_lab/data`, dbt models, and contract tests.
2. If it changes forecasts, start with `src/perishable_lab/forecasting`, temporal split tests, and forecast metrics.
3. If it changes orders or constraints, start with `src/perishable_lab/inventory`, `src/perishable_lab/decision.py`, and policy tests.
4. If it changes evaluation, start with `src/perishable_lab/evaluation`, reports, and paired comparison tests.
5. If it changes publication, rollback, security, or access control, start with `src/perishable_lab/publication.py`, `src/perishable_lab/security.py`, and runbooks.
6. If it changes operations or review workflows, start with discovery docs, dashboard specs, and monitoring tests.
7. If it is documentation-only, still run the tracked-text hygiene scan and add structure tests when the document has required sections.

When a brief touches multiple areas, choose the smallest path that demonstrates the behavior end to end.
