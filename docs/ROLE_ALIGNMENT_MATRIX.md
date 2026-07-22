# Role Alignment Matrix

| Capability | Evidence |
|---|---|
| Probabilistic forecasting | `src/perishable_lab/forecasting`, `docs/MODEL_CARD.md`, `reports/example_run/forecast_metrics.json` |
| Decision optimization | `src/perishable_lab/inventory/policies.py`, `src/perishable_lab/decision.py`, `docs/POLICY_CARD.md` |
| Simulation and evaluation | `src/perishable_lab/inventory/simulator.py`, `src/perishable_lab/evaluation`, `reports/example_results.md` |
| Data contracts and quality | `src/perishable_lab/data/contracts.py`, `data/README.md`, `docs/DASHBOARD_METRIC_DICTIONARY.md` |
| Production workflow design | `Dockerfile`, `.github/workflows/ci.yml`, `airflow/dags/perishable_decision_pipeline.py`, `gcp/DEPLOYMENT_RUNBOOK.md` |
| Reproducibility | `reports/example_run`, `scripts/release_gate.py`, `scripts/repo_hygiene.py` |
| Risk communication | `docs/FINAL_RELEASE_AUDIT.md`, `docs/FAILURE_ANALYSIS.md`, `docs/issues` |
| Stakeholder communication | `docs/LIVE_DEMO_GUIDE.md`, `docs/DEEP_DIVE_PLAN.md`, `docs/INTERVIEW_WALKTHROUGH.md` |

Use this matrix to map a conversation back to concrete files and testable artifacts.
