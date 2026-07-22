# Interview Question Bank

This bank is grounded in the repository and is written for spoken defense. Each answer includes direct response, technical detail, repository evidence, limitation, and likely follow-up.

## Core Questions

### Q01: Why are point forecasts insufficient for fresh-food ordering?

Direct answer: The order decision depends on the cost of being wrong in each direction, shelf life, lead time, current stock, and constraints, so a single expected value hides the relevant tail risk.

Technical detail: A service policy often orders to a quantile of cumulative protection-horizon demand, not the mean. The quantile depends on the underage and overage costs and can move when shelf life or lead time changes.

Evidence: `docs/FORECAST_DECISION_CONTRACT.md`, `src/perishable_lab/decision.py`, `tests/test_decision.py`.

Limitation: The demo still uses simplified cost assumptions and synthetic data.

Follow-up: When would the median forecast be an acceptable policy input?

### Q02: What makes pinball loss a proper score for quantiles?

Direct answer: Pinball loss is minimized in expectation by the target quantile, so it rewards calibrated quantile predictions.

Technical detail: For quantile level `q`, loss is `(q - 1{y < f})(y - f)`. The expected subgradient is `P(Y <= f) - q`, which is zero at the `q` quantile.

Evidence: `src/perishable_lab/forecasting/metrics.py`, `tests/test_conformal.py`, `docs/MODEL_CARD.md`.

Limitation: Good marginal quantile scores do not guarantee good order decisions.

Follow-up: Why can pinball loss improve while fill rate worsens?

### Q03: How does the repository enforce monotone quantiles?

Direct answer: Predictions are post-processed so higher quantile columns cannot fall below lower quantile columns.

Technical detail: Row-wise cumulative maxima remove crossing after independent quantile regressors are fitted.

Evidence: `src/perishable_lab/forecasting/quantile.py`, `tests/test_decision.py`.

Limitation: Post-processing fixes monotonicity but does not ensure conditional calibration.

Follow-up: What modelling approach could avoid quantile crossing directly?

### Q04: What is conformal calibration doing here?

Direct answer: It expands forecast intervals using calibration residuals from a separated calibration period.

Technical detail: The conformal adjustment is computed from calibration conformity scores and then applied to the lower and upper interval bounds before test evaluation.

Evidence: `src/perishable_lab/forecasting/conformal.py`, `tests/test_conformal.py`, `reports/example_run/forecast_metrics.json`.

Limitation: Split conformal gives marginal coverage under exchangeability, not guaranteed conditional coverage for every segment.

Follow-up: How would you monitor segment undercoverage?

### Q05: What is the difference between marginal and conditional coverage?

Direct answer: Marginal coverage averages over the evaluation population; conditional coverage asks whether coverage holds within a segment or feature condition.

Technical detail: A model can hit 90 percent coverage overall while under-covering promoted items and over-covering non-promoted items.

Evidence: `docs/DASHBOARD_METRIC_DICTIONARY.md`, `tests/test_dashboard.py`, `reports/example_run/coverage_summary.csv`.

Limitation: Small segments can make conditional estimates noisy.

Follow-up: How should sample size affect an alert?

### Q06: How do intermittent-demand products change the modelling problem?

Direct answer: Many zero-demand days make ordinary smooth models overstate certainty and can blur demand occurrence with demand size.

Technical detail: Intermittent demand can use empirical hierarchy fallbacks, zero-adjusted strategies, or separate occurrence and size models.

Evidence: `src/perishable_lab/forecasting/hierarchy.py`, `tests/test_hierarchical_forecasting.py`, `src/perishable_lab/data/synthetic.py`.

Limitation: The repository has baselines, not a fully specialized intermittent-demand production model.

Follow-up: How would you score intermittent forecasts fairly?

### Q07: Why is censored demand a problem?

Direct answer: Observed sales can be lower than latent demand when stock runs out, so training on sales alone can learn stock availability rather than demand.

Technical detail: A stockout day with sales equal to inventory on hand is right-censored; the true demand is at least observed sales.

Evidence: `src/perishable_lab/demand_censoring/strategies.py`, `tests/test_demand_censoring.py`, `docs/LATENT_DEMAND_CARD.md`.

Limitation: Synthetic tests show mechanics, not retailer-specific censoring prevalence.

Follow-up: What data would you need to estimate lost demand?

### Q08: Why use hierarchy for cold starts?

Direct answer: New or sparse products can borrow signal from department, product cluster, or store-level history when product-level data is weak.

Technical detail: Fallback selection should be explicit and auditable so weak granular forecasts do not silently dominate.

Evidence: `src/perishable_lab/forecasting/hierarchy.py`, `docs/HIERARCHICAL_FORECASTING.md`, `tests/test_hierarchical_forecasting.py`.

Limitation: Hierarchy fallback can hide local differences if used too broadly.

Follow-up: How would you decide when to fall back?

### Q09: Why not add daily marginal quantiles across lead time?

Direct answer: Quantiles are nonlinear; adding daily quantiles ignores temporal dependence and usually misstates cumulative risk.

Technical detail: Two days with identical marginal quantiles can have different cumulative quantiles under independent versus comonotonic dependence.

Evidence: `src/perishable_lab/decision.py`, `tests/test_decision.py`, `docs/FORECAST_DECISION_CONTRACT.md`.

Limitation: Scenario paths need a defensible dependence assumption.

Follow-up: What dependence assumptions are conservative?

### Q10: What is the newsvendor critical fractile?

Direct answer: The optimal order-up-to quantile is `Cu / (Cu + Co)`, where `Cu` is underage cost and `Co` is overage cost.

Technical detail: Underage cost is lost margin or service penalty; overage cost is unit cost plus disposal or markdown cost net salvage.

Evidence: `src/perishable_lab/inventory/policies.py`, `tests/test_inventory.py`, `docs/BUSINESS_PARAMETERS.md`.

Limitation: The formula is static and simplified relative to multi-period perishable inventory.

Follow-up: What changes when shelf life spans multiple days?

### Q11: How are service constraints represented?

Direct answer: Service can be represented through a target quantile, fill-rate guardrail, or constrained optimization objective.

Technical detail: The robust ordering module separates cost objective from service and feasibility constraints.

Evidence: `src/perishable_lab/inventory/optimization.py`, `tests/test_inventory_optimization.py`, `docs/INVENTORY_OPTIMIZATION.md`.

Limitation: Global service constraints can hide harmed segments unless monitored by store and product group.

Follow-up: How would you enforce segment-level service floors?

### Q12: What inventory state does the simulator keep?

Direct answer: It keeps FIFO shelf-life cohorts and pending pipeline deliveries.

Technical detail: On each day, stock ages and expires, deliveries arrive, shrinkage occurs, demand is fulfilled FIFO, and the policy sees a noisy stock record.

Evidence: `src/perishable_lab/inventory/simulator.py`, `tests/test_simulator_vv.py`, `docs/SIMULATOR_CARD.md`.

Limitation: Store-specific receiving behavior must be validated with operators.

Follow-up: Which event order would you confirm during store discovery?

### Q13: What invariants protect the simulator from silent accounting bugs?

Direct answer: Demand conservation, non-negative stock, non-negative orders, supplier fill not exceeding orders, and deterministic replay.

Technical detail: Fulfilled plus lost sales equals demand; waste equals expiry plus shrinkage; output is reproducible for the same seed.

Evidence: `tests/test_properties.py`, `tests/test_simulator_vv.py`, `artifacts/simulator_vv/validation_gate.json`.

Limitation: Invariants prove accounting consistency, not real-world validity.

Follow-up: What invariant would you add for returns or transfers?

### Q14: How is hidden inventory handled?

Direct answer: Hidden inventory is treated as uncertainty in the inventory belief rather than a known state.

Technical detail: Reconciliation logic captures confidence and discrepancy causes; decision contracts reject stale snapshots.

Evidence: `src/perishable_lab/inventory/reconciliation.py`, `tests/test_inventory_reconciliation.py`, `docs/INVENTORY_BELIEF.md`.

Limitation: Real hidden stock requires count process data and store workflow evidence.

Follow-up: How would you distinguish theft, shrinkage, and back-room stock?

### Q15: How is shelf-life risk represented?

Direct answer: Shelf-life distributions and expiry risk are explicit inputs that change how useful on-hand inventory is.

Technical detail: Age-aware policies discount expiring inventory when computing the order request.

Evidence: `src/perishable_lab/shelf_life/models.py`, `tests/test_shelf_life.py`, `tests/test_inventory.py`.

Limitation: The synthetic shelf-life generator is not calibrated to actual product quality labels.

Follow-up: What store data would improve shelf-life estimates?

### Q16: How is supplier reliability modelled?

Direct answer: Supplier fill rate and delivery delay are represented as reliability metrics and simulator controls.

Technical detail: Simulator controls can apply partial fill and lead-time jitter, and supplier reports summarize delay and fill behavior.

Evidence: `src/perishable_lab/supplier.py`, `tests/test_supplier.py`, `src/perishable_lab/inventory/simulator.py`.

Limitation: Supplier disruption correlation across products is not fully modelled.

Follow-up: How would a shared supplier outage affect experiment design?

### Q17: Why separate forecast evaluation from policy evaluation?

Direct answer: Forecast scores measure predictive quality; policy evaluation measures operational consequences.

Technical detail: A forecast can be statistically better on average but worse for high-cost rows, constrained products, or tail decisions.

Evidence: `docs/PORTFOLIO_CASE_STUDY.md`, `src/perishable_lab/evaluation/reporting.py`, `tests/test_dashboard.py`.

Limitation: Policy evaluation still depends on simulator validity and logged-policy support.

Follow-up: What metric would you use as the primary experiment outcome?

### Q18: What is offline policy evaluation support?

Direct answer: Support means candidate actions overlap sufficiently with historically observed actions.

Technical detail: Inverse propensity methods become unstable when propensities are tiny or candidate actions were rarely observed.

Evidence: `src/perishable_lab/offline.py`, `tests/test_offline.py`, `docs/OFFLINE_POLICY_EVALUATION.md`.

Limitation: Hidden inventory and censored outcomes can violate identification assumptions.

Follow-up: When should offline estimates be reported as not identifiable?

### Q19: Why use shadow mode before live rollout?

Direct answer: Shadow mode produces recommendations without store impact, allowing comparison, telemetry checks, and operational review.

Technical detail: The rollout module separates historical replay, shadow, human review, pilot, field test, and progressive rollout gates.

Evidence: `src/perishable_lab/deployment/rollout.py`, `tests/test_rollout.py`, `docs/ROLLOUT_EXPERIMENTATION.md`.

Limitation: Shadow acceptance does not prove live behavior because operators may act differently under real stakes.

Follow-up: What guardrail would stop the rollout?

### Q20: How would you randomize a field test?

Direct answer: Choose the unit by interference risk: store, department, product cluster, or time block.

Technical detail: Shared displays, substitutions, supplier capacity, and staff learning can contaminate product-level randomization.

Evidence: `docs/ROLLOUT_EXPERIMENTATION.md`, `src/perishable_lab/deployment/rollout.py`, `tests/test_rollout.py`.

Limitation: Power may be limited when store-level randomization is required.

Follow-up: When would stepped-wedge be preferable?

### Q21: How is point-in-time correctness enforced?

Direct answer: Feature rows are joined only when both effective time and availability time are at or before the order cutoff.

Technical detail: Late restatements can keep the original effective date but receive a later availability timestamp, preserving frozen runs.

Evidence: `src/perishable_lab/feature_store.py`, `tests/test_feature_store.py`, `docs/FEATURE_STORE_LINEAGE.md`.

Limitation: Upstream systems still need reliable timestamp semantics.

Follow-up: What timestamp fields must be defined?

### Q22: How does the repository prevent partial publication?

Direct answer: It stages immutable batches, validates them, then atomically swaps an active pointer.

Technical detail: Store-facing readers follow only the active pointer and artifact hash checks prevent corrupted batch reads.

Evidence: `src/perishable_lab/publication.py`, `tests/test_publication.py`, `docs/PUBLICATION_RUNBOOK.md`.

Limitation: Cloud implementation still needs transactional warehouse controls and generation checks.

Follow-up: What happens after a failed partition?

### Q23: What should be in a recommendation explanation?

Direct answer: Forecast version, forecast distribution, stock belief, pending orders, constraints, binding factors, and policy version.

Technical detail: The decision contract persists the inputs needed to replay why a quantity was recommended.

Evidence: `src/perishable_lab/decision.py`, `tests/test_decision.py`, `docs/FORECAST_DECISION_CONTRACT.md`.

Limitation: Explanations must be translated into store workflow language.

Follow-up: How would you explain uncertainty to store staff?

### Q24: What is a proper fallback path?

Direct answer: Use hierarchy forecasts, previous valid batches, manual review, or safe incumbent policy depending on the failure.

Technical detail: Monitoring alert rules map failure conditions to explicit fallbacks and closure conditions.

Evidence: `src/perishable_lab/monitoring/alerts.py`, `tests/test_observability.py`, `docs/OBSERVABILITY_RUNBOOK.md`.

Limitation: Automatic rollback should be limited to deterministic reversible failures.

Follow-up: Which failures should not auto-rollback?

### Q25: How does the project treat overrides?

Direct answer: Overrides are captured with reason, actor, date, store, product, and quantity while preserving the original recommendation.

Technical detail: Override reasons are treated as workflow evidence, not blame.

Evidence: `src/perishable_lab/publication.py`, `src/perishable_lab/discovery.py`, `docs/OVERRIDE_REASON_TAXONOMY.md`.

Limitation: Override labels can be biased by workload and trust.

Follow-up: How would you use overrides in monitoring?

### Q26: How does dbt fit into the architecture?

Direct answer: dbt materializes validated staging tables, feature marts, recommendation marts, and dashboard marts in BigQuery.

Technical detail: Models define uniqueness, not-null tests, partitions, and clustering for batch analytics.

Evidence: `dbt_project/models/schema.yml`, `dbt_project/models/marts/fct_feature_set_daily.sql`, `dbt_project/models/marts/fct_dashboard_daily.sql`.

Limitation: The repo includes example dbt code, not a live warehouse deployment.

Follow-up: Which models should be incremental?

### Q27: Why use Cloud Run Jobs for batch scoring?

Direct answer: The workload is batch-first, date-partitioned, and should be idempotent rather than interactive.

Technical detail: Deterministic job IDs bind retailer, business date, configuration, data version, model, and policy.

Evidence: `src/perishable_lab/publication.py`, `src/perishable_lab/deployment/gcp.py`, `gcp/DEPLOYMENT_RUNBOOK.md`.

Limitation: Long jobs may require chunking or orchestration retries.

Follow-up: When would an HTTP service be justified?

### Q28: What does Airflow orchestrate?

Direct answer: It coordinates validation, feature build, scoring, recommendation, monitoring, and publication gates.

Technical detail: Publication should not proceed when upstream data checks or batch validation fail.

Evidence: `airflow/dags/perishable_lab_daily.py`, `docs/PUBLICATION_RUNBOOK.md`.

Limitation: Retry storms need monitoring and deduplication.

Follow-up: How would you handle a retry storm?

### Q29: How is testing focused beyond line coverage?

Direct answer: Tests target silent numerical, temporal, and inventory-accounting failures.

Technical detail: Property-style checks cover conservation, monotone policies, deterministic replay, point-in-time correctness, and stable schemas.

Evidence: `docs/TEST_STRATEGY.md`, `tests/test_properties.py`, `configs/mutation_testing.example.yaml`.

Limitation: Real store behavior cannot be fully tested without field data.

Follow-up: What mutation target matters most?

### Q30: What security separation matters most?

Direct answer: Data read, training, policy approval, publication, override, and audit roles must be separated.

Technical detail: A principal that can approve and publish can bypass governance, so the policy rejects that combination.

Evidence: `src/perishable_lab/security.py`, `tests/test_security.py`, `docs/IAM_MATRIX.md`.

Limitation: Cloud IAM still needs enforcement in the deployment environment.

Follow-up: How are secrets handled?

### Q31: What dashboard mistake is the project trying to avoid?

Direct answer: Hiding harmed segments under aggregate improvement.

Technical detail: Metrics carry denominators, sample sizes, timing, uncertainty, thresholds, and drill-down links.

Evidence: `src/perishable_lab/dashboard.py`, `tests/test_dashboard.py`, `docs/DASHBOARD_METRIC_DICTIONARY.md`.

Limitation: Dashboard fields still need live semantic-layer governance.

Follow-up: How do you separate leading indicators from outcomes?

### Q32: How do you protect against noisy alerts?

Direct answer: Each alert has a minimum sample, deduplication key, threshold, owner, fallback, and closure condition.

Technical detail: Small-sample branches are suppressed rather than paged.

Evidence: `src/perishable_lab/monitoring/alerts.py`, `tests/test_observability.py`, `configs/alert_rules.example.yaml`.

Limitation: Thresholds require calibration after live baseline observation.

Follow-up: Which alert should page first?

### Q33: How is cost engineering handled?

Direct answer: Benchmark workloads measure wall time, CPU time, peak memory, throughput, and estimated cloud cost before optimization.

Technical detail: The performance harness keeps a reference implementation for parity and checks chunked scoring for row preservation.

Evidence: `src/perishable_lab/performance.py`, `tests/test_performance.py`, `docs/PERFORMANCE_SCALING.md`.

Limitation: Local benchmarks do not substitute for production traces.

Follow-up: When would you parallelize?

### Q34: How do store interviews affect the modelling roadmap?

Direct answer: Observations become assumption evidence and product or data hypotheses with measurable outcomes.

Technical detail: A proposed enhancement must link workflow problem, required data, validation method, and acceptance criteria.

Evidence: `src/perishable_lab/discovery.py`, `tests/test_discovery.py`, `docs/STORE_DISCOVERY_GUIDE.md`.

Limitation: Anecdotes are not treated as ground truth without repeated or measured evidence.

Follow-up: How would you protect staff from blame?

### Q35: What is the biggest unproven claim?

Direct answer: Real retailer impact is not proven by this repository.

Technical detail: The committed example uses synthetic data and tests software behavior, not commercial lift.

Evidence: `docs/CLAIMS_AUDIT.md`, `docs/PORTFOLIO_CASE_STUDY.md`, `reports/example_results.md`.

Limitation: Field impact requires retailer data, shadow mode, and controlled experimentation.

Follow-up: What would you do in the first 90 days?

### Q36: Why does product identity affect forecasts?

Direct answer: If identifiers split or merge incorrectly, the training history no longer represents the item being forecast.

Technical detail: The resolver maintains effective-dated mappings and confidence states for as-of lookup.

Evidence: `src/perishable_lab/product_identity/resolution.py`, `tests/test_product_identity.py`, `dbt_project/models/marts/dim_product_identity.sql`.

Limitation: Matching rules need retailer-specific validation.

Follow-up: How do remaps affect frozen training runs?

### Q37: What is a stockout-censoring sensitivity bound?

Direct answer: It is a conservative range showing how much value estimates could move under hidden lost demand or inventory uncertainty.

Technical detail: The offline module returns bounds rather than a confident estimate when identification is weak.

Evidence: `src/perishable_lab/offline.py`, `tests/test_offline.py`.

Limitation: Bounds can be too wide to select a policy.

Follow-up: What data would narrow the bounds?

### Q38: How do price and promotion features avoid leakage?

Direct answer: They use only event or calendar records known by the decision cutoff.

Technical detail: Known-at timestamps filter promotion and calendar rows before feature creation.

Evidence: `src/perishable_lab/events.py`, `tests/test_events.py`, `docs/EVENT_EFFECTS.md`.

Limitation: Predictive promotion effects are not causal incrementality.

Follow-up: How would you estimate causal promotion lift?

### Q39: Why is row-level access relevant to dashboards?

Direct answer: Store views should not expose other stores or restricted override details to unauthorized users.

Technical detail: Dashboard access functions filter by allowed store IDs and semantic fields mark restricted access.

Evidence: `src/perishable_lab/dashboard.py`, `tests/test_dashboard.py`, `docs/DASHBOARD_SEMANTIC_LAYER.md`.

Limitation: Production access control must be enforced by the serving layer.

Follow-up: Which field is restricted?

### Q40: How is artifact provenance represented?

Direct answer: Artifact hashes are bound to configuration, data manifest, and code revision.

Technical detail: Approval records must match artifact ID and hash before publication.

Evidence: `src/perishable_lab/security.py`, `tests/test_security.py`, `docs/SECURITY_GOVERNANCE.md`.

Limitation: Real signing infrastructure is described, not deployed here.

Follow-up: What should happen after artifact hash mismatch?

### Q41: How would you compare two models fairly?

Direct answer: Use the same temporal split, feature availability rules, calibration process, and decision policy evaluation.

Technical detail: The comparison should report proper scoring rules, calibration, segment metrics, and downstream policy KPIs.

Evidence: `src/perishable_lab/evaluation/splits.py`, `docs/MODEL_CARD.md`, `docs/DASHBOARD_METRIC_DICTIONARY.md`.

Limitation: Synthetic comparison cannot determine field impact.

Follow-up: What if the better model is slower?

### Q42: Why does lead time affect the forecast target?

Direct answer: The order protects demand during review period plus lead time, so the forecast horizon must match that cumulative exposure.

Technical detail: If lead time is two days and review is one day, the policy needs a three-day cumulative demand distribution.

Evidence: `src/perishable_lab/decision.py`, `tests/test_decision.py`, `src/perishable_lab/forecasting/horizon.py`.

Limitation: Lead-time variability requires scenario or reliability modelling.

Follow-up: What happens when lead time is uncertain?

### Q43: How do case packs change optimal orders?

Direct answer: They discretize feasible orders, so the unconstrained optimum may be infeasible.

Technical detail: The constrained policy rounds to case packs and respects minimum order and storage capacity.

Evidence: `src/perishable_lab/inventory/policies.py`, `tests/test_inventory.py`.

Limitation: Physical store constraints can differ from master data.

Follow-up: How would you validate case packs in-store?

### Q44: What is deterministic replay?

Direct answer: The same inputs, seed, configuration, and artifacts reproduce the same result.

Technical detail: Run manifests, feature hashes, source partition manifests, and deterministic job IDs support replay.

Evidence: `src/perishable_lab/feature_store.py`, `src/perishable_lab/publication.py`, `tests/test_properties.py`.

Limitation: External systems must preserve source partitions.

Follow-up: Which hash would you check first?

### Q45: Why separate model card, policy card, simulator card, and system card?

Direct answer: Each artifact has different assumptions, evidence, and failure modes.

Technical detail: Model quality does not imply policy safety, and simulator verification does not imply field validity.

Evidence: `docs/MODEL_CARD.md`, `docs/POLICY_CARD.md`, `docs/SIMULATOR_CARD.md`, `docs/SYSTEM_CARD.md`.

Limitation: Cards require human review to stay meaningful.

Follow-up: What card changes after a new feature interface?

### Q46: How does the project handle missing rows in a batch?

Direct answer: Publication validation blocks staging when expected row counts are not met.

Technical detail: Missing rows, duplicates, stale model versions, unit mismatches, stale inputs, and jumps are blocking issues.

Evidence: `src/perishable_lab/publication.py`, `tests/test_publication.py`.

Limitation: Expected rows must be computed correctly upstream.

Follow-up: What should stores see during the failure?

### Q47: What is the purpose of a golden scenario?

Direct answer: It checks a hand-computable event sequence that should not drift.

Technical detail: The simulator output is compared row-by-row against a committed fixture.

Evidence: `tests/fixtures/golden_simulation_expected.csv`, `tests/test_simulator_vv.py`.

Limitation: One golden scenario cannot cover all store processes.

Follow-up: What second golden scenario would you add?

### Q48: Why is experiment sample-ratio mismatch important?

Direct answer: It can reveal assignment bugs or contamination that invalidate the test.

Technical detail: Assignment balance is checked against expected treatment fraction with an alert threshold.

Evidence: `src/perishable_lab/deployment/rollout.py`, `tests/test_rollout.py`.

Limitation: Perfect balance is not required, but large unexplained deviations are risky.

Follow-up: What causes contamination?

### Q49: How do you define a primary experiment outcome?

Direct answer: Combine waste and availability while enforcing guardrails so one cannot improve by sacrificing the other beyond an agreed limit.

Technical detail: The rollout plan defines balanced loss plus standalone availability, waste, incident, override, volatility, and fairness guardrails.

Evidence: `docs/ROLLOUT_EXPERIMENTATION.md`, `src/perishable_lab/deployment/rollout.py`.

Limitation: Outcome windows must handle delayed waste and sales reporting.

Follow-up: How would you handle multiple metrics?

### Q50: How are late outcomes handled in dashboards?

Direct answer: Leading indicators are shown separately from outcomes that arrive later.

Technical detail: Metrics can be computed as-of a timestamp; outcome rows after that timestamp are excluded while leading metrics remain visible.

Evidence: `src/perishable_lab/dashboard.py`, `tests/test_dashboard.py`, `docs/DASHBOARD_FRESHNESS.md`.

Limitation: Users need clear banners for incomplete outcome windows.

Follow-up: Which metrics are leading?

### Q51: Why is dynamic SQL identifier validation needed?

Direct answer: Dynamic identifiers can become an injection path if not constrained.

Technical detail: The security module only allows safe dotted warehouse identifiers.

Evidence: `src/perishable_lab/security.py`, `tests/test_security.py`.

Limitation: Query parameters and IAM are still required.

Follow-up: What should never be string-interpolated?

### Q52: What is the role of mutation testing?

Direct answer: It tests whether critical logic fails when arithmetic, branching, or temporal conditions are intentionally changed.

Technical detail: The configured targets are simulator, policy, decision, feature store, and publication modules.

Evidence: `configs/mutation_testing.example.yaml`, `reports/test_assurance/mutation_score.json`, `docs/TEST_STRATEGY.md`.

Limitation: The committed score is a release-gate record, not an exhaustive mutation campaign.

Follow-up: Which mutant would concern you most?

### Q53: How do you communicate uncertainty to operators?

Direct answer: Translate uncertainty into review status, range, reason, and action rather than statistical jargon.

Technical detail: A store drill-down shows forecast interval, stock belief, pending orders, shelf-life cohorts, explanation, and override reason.

Evidence: `docs/DASHBOARD_WIREFRAMES.md`, `src/perishable_lab/dashboard.py`, `docs/STORE_DISCOVERY_GUIDE.md`.

Limitation: The exact wording needs user testing with store staff.

Follow-up: What should a store manager see first?

### Q54: How would you debug a sudden waste increase?

Direct answer: Check harmed segments, recent promotions, stock beliefs, supplier changes, shelf-life cohorts, and publication version.

Technical detail: The dashboard links portfolio waste to store-product drill-downs and alerts link to runbooks.

Evidence: `docs/DASHBOARD_SQL_EXAMPLES.md`, `tests/test_dashboard.py`, `docs/OBSERVABILITY_RUNBOOK.md`.

Limitation: Waste reporting can arrive late or be inconsistently recorded.

Follow-up: How do you avoid blaming store staff?

### Q55: What is an idempotent batch job?

Direct answer: Re-running the same logical job with the same inputs produces the same job ID and output location.

Technical detail: Job IDs include retailer, business date, config hash, data version, model version, and policy version.

Evidence: `src/perishable_lab/publication.py`, `tests/test_publication.py`.

Limitation: Idempotency depends on immutable inputs.

Follow-up: What happens when the artifact differs under the same ID?

### Q56: Why keep a reference implementation for performance work?

Direct answer: Optimization can change results silently; the reference provides a correctness oracle.

Technical detail: The performance module compares vectorized panel summaries to readable group-by logic.

Evidence: `src/perishable_lab/performance.py`, `tests/test_performance.py`.

Limitation: Reference code may be too slow for production but useful in tests.

Follow-up: What optimization order do you follow?

### Q57: What makes a good release checklist?

Direct answer: It ties interface changes, assumptions, metrics, tests, cards, security, and operational runbooks together.

Technical detail: Card gates require metric artifacts, evidence-linked claims, and interface coverage.

Evidence: `src/perishable_lab/cards.py`, `tests/test_cards.py`, `docs/CARD_RELEASE_CHECKLIST.md`.

Limitation: Checklists can go stale without ownership.

Follow-up: Who should approve a policy card update?

### Q58: What should be logged for audit without exposing sensitive details?

Direct answer: Actor, environment, resource, action, timestamp, redacted metadata, and stable event hash.

Technical detail: Sensitive keys such as token, secret, password, customer, staff, and employee are redacted.

Evidence: `src/perishable_lab/security.py`, `tests/test_security.py`.

Limitation: Production logs need central retention and access controls.

Follow-up: How long should logs be retained?

### Q59: What does the first 90 days plan prioritize?

Direct answer: Source validation, workflow discovery, stockout and inventory measurement, shadow recommendations, and controlled evaluation.

Technical detail: It avoids broad rollout until data contracts, operational workflows, and guardrails are validated.

Evidence: `docs/PORTFOLIO_CASE_STUDY.md`, `docs/STORE_DISCOVERY_GUIDE.md`, `docs/ROLLOUT_EXPERIMENTATION.md`.

Limitation: Timeline depends on retailer data access and operations availability.

Follow-up: What would you do if data quality is poor?

### Q60: What is the strongest production judgement in the repo?

Direct answer: The system blocks unsafe publication instead of assuming the forecast is always usable.

Technical detail: Validation, monitoring, approval separation, rollback, and store-facing contracts are all explicit.

Evidence: `src/perishable_lab/publication.py`, `src/perishable_lab/monitoring/alerts.py`, `src/perishable_lab/security.py`.

Limitation: Real deployment still needs cloud IAM, warehouse transactions, and operational drills.

Follow-up: What failure would you rehearse first?

## Challenge Mode

### Q61: Can you add `q90` for day one and `q90` for day two to get two-day `q90`?

Direct answer: No.

Technical detail: Quantiles are nonlinear and depend on joint dependence.

Evidence: `tests/test_decision.py`.

Limitation: Scenario paths need a dependence assumption.

Follow-up: Show a counterexample with independent versus comonotonic demand.

### Q62: Does a promotion feature prove causal uplift?

Direct answer: No.

Technical detail: Promotion assignment is confounded by seasonality, product selection, display, and expected demand.

Evidence: `docs/EVENT_EFFECTS.md`, `src/perishable_lab/events.py`.

Limitation: Causal claims need a separate design.

Follow-up: What experiment would estimate incrementality?

### Q63: Does 90 percent marginal coverage mean every store has 90 percent coverage?

Direct answer: No.

Technical detail: Marginal coverage can hide segment undercoverage.

Evidence: `tests/test_dashboard.py`.

Limitation: Segment coverage needs enough sample size.

Follow-up: How should alerts handle small segments?

### Q64: Can a simulator be tuned until the candidate policy wins?

Direct answer: That would be overfitting the simulator.

Technical detail: Parameters must be calibrated on separated data and sensitivity ranges reported.

Evidence: `docs/SIMULATOR_VV_REPORT.md`, `docs/BUSINESS_PARAMETERS.md`.

Limitation: Predictive validity requires real outcomes.

Follow-up: Which assumptions would you stress first?

### Q65: Can you estimate policy value if candidate actions never appear in logs?

Direct answer: No confident point estimate is identifiable.

Technical detail: Lack of overlap makes inverse-propensity and doubly robust estimates invalid or unstable.

Evidence: `src/perishable_lab/offline.py`, `tests/test_offline.py`.

Limitation: You may report bounds or run a new experiment.

Follow-up: What diagnostic should fail?

### Q66: Is lower waste always better?

Direct answer: No.

Technical detail: Lower waste from under-ordering can damage availability and margin.

Evidence: `reports/example_results.md`, `docs/DASHBOARD_METRIC_DICTIONARY.md`.

Limitation: Business priorities define acceptable trade-offs.

Follow-up: What guardrail prevents this?

### Q67: Can a stale inventory snapshot be used if the forecast is strong?

Direct answer: No.

Technical detail: Decision contracts reject inventory observations after the order cutoff.

Evidence: `tests/test_decision.py`.

Limitation: Fallback may still publish previous valid recommendations.

Follow-up: What alert should fire?

### Q68: If fixed service level wins synthetic cost, should it be rolled out?

Direct answer: No.

Technical detail: Synthetic results are scenario evidence, not field impact.

Evidence: `docs/CLAIMS_AUDIT.md`.

Limitation: Real retailer validation is required.

Follow-up: What comes before rollout?

### Q69: Can dashboard aggregate availability prove no store was harmed?

Direct answer: No.

Technical detail: Aggregate numerator and denominator can hide segment degradation.

Evidence: `tests/test_dashboard.py`.

Limitation: Segment thresholds require governance.

Follow-up: Which drill-down would you open?

### Q70: Should all critical alerts automatically rollback?

Direct answer: No.

Technical detail: Only deterministic reversible failures should auto-rollback; ambiguous business issues need review.

Evidence: `src/perishable_lab/monitoring/alerts.py`.

Limitation: Thresholds need live calibration.

Follow-up: Name one auto and one non-auto rollback case.

### Q71: Can one production identity read data, approve, publish, and audit?

Direct answer: No.

Technical detail: Least privilege separates these actions and rejects all-powerful principals.

Evidence: `src/perishable_lab/security.py`, `tests/test_security.py`.

Limitation: Cloud IAM must enforce this outside the package.

Follow-up: Which roles must be separate?

### Q72: Is line coverage enough for confidence?

Direct answer: No.

Technical detail: The tests focus on invariants, temporal correctness, mutation targets, and golden scenarios.

Evidence: `docs/TEST_STRATEGY.md`, `tests/test_properties.py`.

Limitation: Real operations still need field validation.

Follow-up: Which invariant catches stock accounting errors?

### Q73: Can staff overrides be treated as labels of model error?

Direct answer: Not directly.

Technical detail: Overrides reflect trust, workload, missing information, local events, and workflow constraints.

Evidence: `docs/OVERRIDE_REASON_TAXONOMY.md`, `src/perishable_lab/discovery.py`.

Limitation: Some overrides are noisy or incomplete.

Follow-up: How would you use override reasons safely?

### Q74: Can backtests use random row splits?

Direct answer: Not for time-dependent forecasting.

Technical detail: Temporal splits avoid training on future information.

Evidence: `src/perishable_lab/evaluation/splits.py`.

Limitation: Even temporal backtests may not capture regime shifts.

Follow-up: How would you validate a promotion season?

### Q75: Does a clean warehouse write mean stores saw the right recommendation?

Direct answer: Not necessarily.

Technical detail: Publication state, active pointer, store-facing contract, and downstream reads must all be checked.

Evidence: `src/perishable_lab/publication.py`, `docs/PUBLICATION_RUNBOOK.md`.

Limitation: Store-system integration is outside the local demo.

Follow-up: What should the on-call dashboard show?

## Whiteboard Derivations

### Critical Fractile

Let `Q` be order quantity and `D` demand. Underage cost `Cu` applies when `D > Q`; overage cost `Co` applies when `Q > D`.

```text
Expected marginal benefit of one more unit = Cu * P(D > Q)
Expected marginal cost of one more unit = Co * P(D <= Q)
Set equal:
Cu * (1 - F(Q)) = Co * F(Q)
F(Q) = Cu / (Cu + Co)
```

Evidence: `src/perishable_lab/inventory/policies.py`, `tests/test_inventory.py`.

### Pinball Loss

For quantile `q` and forecast `f`:

```text
L_q(y, f) = (q - 1{y < f})(y - f)
E derivative with respect to f = P(Y <= f) - q
Minimum when F(f) = q
```

Evidence: `src/perishable_lab/forecasting/metrics.py`.

### Conformal Interval Adjustment

For lower `l_i`, upper `u_i`, and observed `y_i` on calibration data:

```text
s_i = max(l_i - y_i, y_i - u_i, 0)
adjustment = quantile(s, 1 - alpha)
new lower = l - adjustment
new upper = u + adjustment
```

Evidence: `src/perishable_lab/forecasting/conformal.py`, `tests/test_conformal.py`.

### Lead-Time Demand

For review period `R` and lead time `L`, protection horizon is `H = R + L`.

```text
D_H = sum_{t=1}^{H} D_t
Need distribution of D_H, not sum of marginal quantiles
```

Evidence: `src/perishable_lab/decision.py`, `src/perishable_lab/forecasting/horizon.py`.

### Stock Conservation

For a day after arrivals and shrinkage:

```text
opening stock = fulfilled + ending stock
demand = fulfilled + lost sales
waste = expired + shrinkage
```

Evidence: `src/perishable_lab/inventory/simulator.py`, `tests/test_properties.py`.

### Basic Service-Constrained Optimization

Choose quantity `Q`:

```text
minimize E[c_h ending_inventory + c_w waste + c_s lost_sales]
subject to P(D_H <= Q + inventory_position) >= service_target
and Q satisfies case pack, minimum order, and capacity constraints
```

Evidence: `src/perishable_lab/inventory/optimization.py`, `tests/test_inventory_optimization.py`.
