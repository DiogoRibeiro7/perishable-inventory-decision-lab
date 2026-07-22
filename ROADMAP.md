# Delivery Roadmap To 1.0.0

This roadmap turns the current `0.1.0` portfolio-grade release into a `1.0.0` decision-system release. The target is not to claim field impact from synthetic evidence. The target is to make the package technically ready for audited shadow evaluation, controlled pilot use, and repeatable public benchmarking.

## Roadmap Principles

- Correctness before model complexity.
- Every release must produce an executable end-to-end increment.
- Public package boundaries should stay stable after `0.5.0`; any breaking change must be completed before `1.0.0-rc.1`.
- The local demo path must keep working: `poetry run perishable-lab demo`.
- Synthetic evidence must remain clearly labelled as synthetic.
- A release is not ready unless it includes tests, documentation, rollback notes, and updated cards when behavior changes.
- Cloud and warehouse features must remain optional unless the release explicitly changes installation requirements.

## Version Ladder

| Version | Theme | Release outcome |
|---|---|---|
| `0.2.0` | Demand contracts and censored sales | Canonical data distinguishes observed sales from likely latent demand under stockout conditions. |
| `0.3.0` | Scoring parity and calibration | Forecast scoring uses persisted vocabularies and reports segment-level calibration. |
| `0.4.0` | Simulator validity and policy constraints | Inventory event order is configurable and policy selection can enforce service floors. |
| `0.5.0` | Public benchmark baseline | A user-provided public retail dataset path is reproducible, documented, and separated from synthetic examples. |
| `0.6.0` | Warehouse and orchestration checks | dbt and Airflow examples are validated in CI, with optional cloud dry-runs. |
| `0.7.0` | Observability and publication hardening | Monitoring, batch publication, rollback, and freshness checks have stronger contracts. |
| `0.8.0` | Operator workflow and shadow evaluation | Review, override, and feedback flows are represented in artifacts and reports. |
| `0.9.0` | Release candidate hardening | Interfaces freeze, compatibility is tested, and documentation is reviewed as a release package. |
| `1.0.0` | Stable decision-system release | The repository exposes a stable local API, CLI, documented schemas, reproducible examples, and operational readiness evidence. |

## Cross-Version Quality Gates

Every release from `0.2.0` onward must pass:

- `poetry check`
- `poetry run ruff check .`
- `poetry run mypy src`
- `poetry run pytest`
- `poetry run python scripts/repo_hygiene.py`
- `poetry run python scripts/release_gate.py --write reports/release/vX.Y.Z_gate.json`
- Docker image build in CI.
- Public wording scan for excluded local-development terms.
- Markdown link validation through the release gate.

Every release from `0.5.0` onward must additionally include:

- Updated `docs/RELEASE_NOTES.md`.
- Updated model, policy, simulator, and system cards when assumptions or interfaces change.
- At least one committed compact example artifact or a documented reason not to commit it.
- A rollback path for any new publication, warehouse, or serving behavior.

## `0.2.0`: Demand Contracts And Censored Sales

### Goal

Separate observed sales from demand signals that may be censored by zero stock, low stock, late inventory updates, or known store-operation gaps.

### Scope

- Add `is_censored_demand` to canonical daily rows.
- Add `censoring_reason` with values such as `zero_stock`, `insufficient_stock`, `missing_stock_snapshot`, and `late_stock_snapshot`.
- Add training controls for excluding, down-weighting, or reporting censored rows.
- Add a metrics block for censored-row rate by store, product, demand-volume band, and shelf-life band.
- Preserve current behavior when the new fields are missing.

### Implementation areas

- `src/perishable_lab/data/canonical.py`
- `src/perishable_lab/data/contracts.py`
- `src/perishable_lab/features.py`
- `src/perishable_lab/forecasting/quantile.py`
- `src/perishable_lab/pipelines/demo.py`
- `dbt_project/models/`

### Acceptance gates

- `tests/test_retail_adapter.py` covers zero sales with zero stock and asserts censored-demand output.
- Feature tests prove censored columns survive feature generation without leakage.
- Forecast tests compare include, exclude, and down-weight modes.
- Demo metrics include censored-row counts and rates.
- README limitations and `docs/LATENT_DEMAND_CARD.md` are updated.

### Metrics

- Censored-row rate by segment.
- Forecast pinball loss with and without censored-row handling.
- Coverage delta on censored-heavy slices.
- Percentage of scoring rows with unknown or missing stock context.

### Migration and rollback

- Migration: add nullable canonical fields and treat missing values as uncensored.
- Rollback: disable censoring-aware training while keeping the fields in output schemas.

### Release blockers

- Censored rows silently dropped without metrics.
- Any output schema change without card and README updates.
- Any demo result that claims demand recovery from synthetic data as field evidence.

## `0.3.0`: Stable Scoring And Segment Calibration

### Goal

Make train-time and score-time feature encoding stable, then extend forecast calibration from global-only diagnostics to segment-aware diagnostics and adjustment.

### Scope

- Persist store and product vocabularies with model artifacts.
- Add unknown-category behavior for cold-start stores and products.
- Add a feature schema hash and feature-set version to forecast outputs.
- Report calibration by store group, product class, promotion flag, shelf-life band, demand-volume band, and intermittent-demand flag.
- Add segment conformal adjustment with minimum sample thresholds and fallback to global adjustment.

### Implementation areas

- `src/perishable_lab/features.py`
- `src/perishable_lab/forecasting/quantile.py`
- `src/perishable_lab/forecasting/conformal.py`
- `src/perishable_lab/monitoring/quality.py`
- `docs/FEATURE_STORE_LINEAGE.md`
- `docs/MODEL_CARD.md`

### Acceptance gates

- Feature tests prove a filtered scoring frame uses the same category encodings as the training frame.
- Forecast serialization tests prove vocabularies and feature schema hashes round-trip.
- Conformal tests include at least two noise segments and assert segment-specific adjustment.
- Monitoring tests fail on priority-segment undercoverage.
- `reports/example_run/forecast_metrics.json` includes global and segment summaries.

### Metrics

- Unknown-category rate.
- Global interval coverage.
- Minimum priority-segment coverage.
- Mean interval width by segment.
- Fallback-to-global calibration rate.

### Migration and rollback

- Migration: add model artifact metadata for vocabularies and feature schema.
- Rollback: keep persisted vocabularies but disable segment-specific calibration.

### Release blockers

- Any scorer that recomputes category codes from only the scoring batch.
- Segment calibration without a minimum sample threshold.
- Monitoring alerts that do not identify the affected segment.

## `0.4.0`: Simulator Validity And Constrained Policy Selection

### Goal

Make operational assumptions explicit in the simulator and prevent policy promotion based only on aggregate cost.

### Scope

- Add named simulator event-order modes for receiving, expiry, shrinkage, sales, and order placement.
- Preserve current event order as the default.
- Add sensitivity reports for one-day and two-day shelf-life items.
- Add policy selection that minimizes cost subject to global and segment fill-rate floors.
- Add rejected-policy reasons and feasible-frontier reporting.

### Implementation areas

- `src/perishable_lab/inventory/simulator.py`
- `src/perishable_lab/inventory/policies.py`
- `src/perishable_lab/evaluation/reporting.py`
- `src/perishable_lab/pipelines/demo.py`
- `docs/MODELLING_DECISIONS.md`
- `docs/POLICY_CARD.md`
- `docs/SIMULATOR_CARD.md`

### Acceptance gates

- Inventory tests prove different event-order modes produce expected differences on short shelf-life fixtures.
- Policy tests prove the cheapest policy is rejected when it violates a service floor.
- Reports include selected policy, feasible policies, rejected policies, and violated constraints.
- Simulator outputs include event-order mode and policy version.

### Metrics

- Fill-rate delta by event-order mode.
- Waste-rate delta by event-order mode.
- Total cost among feasible policies.
- Minimum segment fill rate.
- Constraint violation count.

### Migration and rollback

- Migration: add `event_order_mode`, `constraint_status`, `violated_constraints`, and `selected` fields.
- Rollback: set event order to the current default and disable automatic policy promotion.

### Release blockers

- Policy promotion without constraint audit output.
- Event-order changes that alter existing defaults without release-note disclosure.
- Reports that hide infeasible or rejected policies.

## `0.5.0`: Public Benchmark Baseline

### Goal

Add a reproducible public retail benchmark path that is clearly separated from synthetic examples and does not require committing raw third-party data.

### Scope

- Harden the user-provided M5 dataset adapter.
- Add fixture-backed conversion tests for the public benchmark path.
- Add benchmark configuration files with documented assumptions.
- Produce compact benchmark summaries that can be regenerated locally.
- Keep raw external files outside version control.

### Implementation areas

- `src/perishable_lab/data/public_retail.py`
- `src/perishable_lab/data/adapters.py`
- `src/perishable_lab/cli.py`
- `configs/`
- `docs/PUBLIC_RETAIL_DATASET_CARD.md`
- `reports/`

### Acceptance gates

- Adapter tests cover missing files, schema mismatches, calendar joins, price joins, and product mapping.
- Benchmark command is documented and exits with clear errors when raw files are absent.
- A compact committed benchmark report states dataset license, assumptions, split windows, and unavailable operational fields.
- Synthetic demo remains unchanged.

### Metrics

- Pinball loss.
- Interval coverage and width.
- Approximate CRPS.
- Runtime and peak memory for the benchmark profile.
- Missing operational field count and fallback count.

### Migration and rollback

- Migration: add explicit benchmark configs and adapter interfaces without changing synthetic defaults.
- Rollback: disable benchmark command path while preserving local synthetic demo.

### Release blockers

- Committed raw external data.
- Benchmark claims that depend on unavailable inventory or waste fields.
- Public dataset assumptions omitted from the dataset card.

## `0.6.0`: Warehouse And Orchestration Verification

### Goal

Turn cloud and warehouse examples from static scaffolds into validated examples with dry-run checks and clear operational boundaries.

### Scope

- Add dbt parse/build validation against fixture data.
- Add Airflow DAG import validation in CI.
- Add optional BigQuery publication dry-run tests behind environment variables.
- Add service-account and IAM validation helpers.
- Document partition overwrite and rollback command sequences.

### Implementation areas

- `dbt_project/`
- `airflow/dags/`
- `src/perishable_lab/deployment/`
- `.github/workflows/ci.yml`
- `gcp/DEPLOYMENT_RUNBOOK.md`
- `docs/IAM_MATRIX.md`

### Acceptance gates

- CI runs dbt validation without requiring cloud credentials.
- CI imports the DAG and verifies required task IDs.
- Deployment tests verify delete-and-insert ordering through a fake client.
- Optional cloud dry-run tests are skipped clearly when credentials are absent.

### Metrics

- dbt model count and test count.
- DAG import status.
- Publication dry-run status.
- CI duration by job.

### Migration and rollback

- Migration: place cloud-only dependencies in an optional group.
- Rollback: leave cloud checks optional while keeping Python CI mandatory.

### Release blockers

- CI requiring private credentials.
- Dry-run behavior that can mutate production tables.
- Deployment docs without rollback commands.

## `0.7.0`: Observability And Publication Hardening

### Goal

Strengthen run manifests, publication validation, monitoring, and rollback behavior so every published recommendation batch is traceable and reversible.

### Scope

- Version the run manifest schema.
- Add source partition manifest hashes.
- Add freshness, completeness, duplicate, and stale-version checks before publication.
- Add runbook links to monitoring alerts.
- Add immutable active-batch pointer semantics for local and warehouse examples.
- Add dependency and container scan guidance to the release checklist.

### Implementation areas

- `src/perishable_lab/publication.py`
- `src/perishable_lab/monitoring/`
- `src/perishable_lab/pipelines/demo.py`
- `docs/PUBLICATION_RUNBOOK.md`
- `docs/OBSERVABILITY_RUNBOOK.md`
- `docs/DASHBOARD_FRESHNESS.md`
- `docs/TEST_STRATEGY.md`

### Acceptance gates

- Publication tests cover partial writes, stale batch versions, duplicate rows, corrupted artifacts, and rollback.
- Monitoring tests include runbook links and severity levels.
- Demo manifest includes schema version, source hashes, config hash, feature-set hash, model version, policy version, and artifact list.
- Dashboard metric dictionary maps each release metric to an owner and blocking threshold.

### Metrics

- Publication completeness.
- Manifest validation status.
- Freshness lag.
- Rollback success rate in fault tests.
- Alert count by severity and component.

### Migration and rollback

- Migration: add a manifest schema version and retain compatibility reader for prior manifests.
- Rollback: publish previous valid batch pointer and preserve failed batch artifacts for audit.

### Release blockers

- Publication without manifest validation.
- Rollback path that deletes failure evidence.
- Alerts without owner, severity, and runbook link.

## `0.8.0`: Operator Workflow And Shadow Evaluation

### Goal

Represent how store and operations users review recommendations, override them, and provide feedback during shadow evaluation.

### Scope

- Add override reason taxonomy to recommendation outputs.
- Add shadow-mode comparison between incumbent orders and candidate recommendations.
- Add operator review artifacts for accepted, edited, rejected, and unavailable recommendations.
- Add feedback-loop metrics for override rate, reason mix, repeated constraints, and review latency.
- Add experiment-readiness checklist for limited pilot use.

### Implementation areas

- `src/perishable_lab/evaluation/`
- `src/perishable_lab/publication.py`
- `src/perishable_lab/monitoring/`
- `docs/OVERRIDE_REASON_TAXONOMY.md`
- `docs/OPERATIONS_FEEDBACK_LOOP.md`
- `docs/ROLLOUT_EXPERIMENTATION.md`
- `docs/STORE_DISCOVERY_GUIDE.md`

### Acceptance gates

- Evaluation tests compare incumbent and candidate recommendations without claiming live impact.
- Publication tests prove override fields do not alter original recommendation lineage.
- Reports include override summary, reason-code distribution, and decision deltas.
- Rollout documentation states stop criteria and review responsibilities.

### Metrics

- Override rate by store and product segment.
- Review latency.
- Candidate-versus-incumbent order delta.
- Repeated constraint count.
- Shadow exception count.

### Migration and rollback

- Migration: add optional override fields and shadow comparison outputs.
- Rollback: disable override ingestion while retaining candidate recommendation publication.

### Release blockers

- Shadow metrics presented as causal lift.
- Override data that overwrites original recommendation fields.
- Missing stop criteria for pilot progression.

## `0.9.0`: Release Candidate Hardening

### Goal

Freeze public interfaces, test compatibility, and prepare the repository for `1.0.0` without known unresolved release blockers.

### Scope

- Freeze public CLI commands and core output schemas.
- Add compatibility tests for previous example manifests where feasible.
- Add schema documentation for canonical data, forecasts, policy metrics, monitoring reports, and run manifests.
- Add release candidate checklist and deprecation policy.
- Audit README, cards, examples, issue templates, and release notes for consistency.

### Implementation areas

- `src/perishable_lab/cli.py`
- `src/perishable_lab/config.py`
- `src/perishable_lab/cards.py`
- `docs/`
- `reports/release/`
- `.github/`

### Acceptance gates

- CLI help snapshots or equivalent command-contract tests pass.
- Schema tests validate all committed example artifacts.
- Release notes include upgrade notes from `0.1.0` to `0.9.0`.
- `docs/FINAL_RELEASE_AUDIT.md` is refreshed for the candidate.
- No unresolved high-severity readiness findings remain.

### Metrics

- Public command count and tested command count.
- Schema validation coverage.
- Documentation link pass rate.
- Release gate status.

### Migration and rollback

- Migration: provide deprecation notes for anything renamed before `1.0.0`.
- Rollback: tag the last pre-candidate release and keep compatibility readers for committed examples.

### Release blockers

- Breaking output schema changes without migration notes.
- Release-facing docs contradicting model, policy, simulator, or system cards.
- Any failing mandatory CI job.

## `1.0.0`: Stable Decision-System Release

### Goal

Ship a stable local-first release with documented contracts, reproducible examples, public benchmark support, verified operational patterns, and explicit limitations.

### Included capability baseline

- Canonical data contracts distinguish observed sales from censored demand indicators.
- Forecasting uses stable scoring metadata and reports segment calibration.
- Simulator event order is explicit and documented.
- Policy selection can enforce global and segment service constraints.
- Synthetic demo and public benchmark paths are reproducible.
- dbt and Airflow examples are validated without private credentials.
- Publication and rollback paths are tested through local or fake-client checks.
- Monitoring outputs include owners, severities, thresholds, and runbook links.
- Operator override and shadow-evaluation artifacts are represented without claiming causal impact.
- Release cards and README align with committed behavior.

### Final acceptance gates

- Full local quality gate passes.
- GitHub Actions passes for all mandatory jobs.
- Release gate writes `reports/release/v1.0.0_gate.json`.
- Docker image builds from the release tag.
- Example artifacts regenerate from documented commands.
- All local markdown links resolve.
- License, citation, Zenodo metadata, and release notes are current.
- `docs/FINAL_RELEASE_AUDIT.md` states remaining limitations and explicitly separates software readiness from field impact.

### Public API and schema stability

The `1.0.0` release freezes:

- CLI command names and required arguments.
- Canonical daily row schema.
- Forecast prediction schema.
- Policy metrics schema.
- Monitoring report schema.
- Run manifest schema.
- Model, policy, simulator, and system card fields.

Breaking changes after `1.0.0` require a documented migration path and a major-version bump.

### Remaining limitations allowed at `1.0.0`

- No retailer outcome claim without retailer field data.
- Optional cloud deployment examples may remain templates unless a live environment is available.
- Public benchmark support may depend on user-provided data files and accepted dataset terms.
- Advanced research models may remain experimental if the baseline path is stable and documented.

### Release blockers

- Any hidden dependency on private credentials or local-only files.
- Any unlabelled synthetic evidence.
- Any failing required check.
- Any high-severity readiness finding without a documented owner, mitigation, and release decision.

## Backlog Beyond `1.0.0`

The following work is intentionally outside the `1.0.0` stability target:

- Multi-echelon inventory optimization.
- Joint probabilistic demand paths across related products.
- Live dashboard deployment.
- Automated retraining governance.
- Store-system integration adapters for specific retailers.
- Online experiment analysis from live treatment/control data.
- Advanced Bayesian inventory belief models.
- Real-time recommendation serving.

## Version Cut Checklist

Use this checklist before tagging each release:

- Version updated in `pyproject.toml`.
- Cards updated if behavior, assumptions, or interfaces changed.
- Release notes include added, changed, fixed, migration, and known limitation sections.
- Example artifacts regenerated or explicitly left unchanged.
- `reports/release/vX.Y.Z_gate.json` written.
- GitHub Actions green on `main`.
- Release tag points to the checked commit.
- Zenodo metadata reviewed for title, creators, ORCID, license, keywords, version, date, and DOI relationship.
