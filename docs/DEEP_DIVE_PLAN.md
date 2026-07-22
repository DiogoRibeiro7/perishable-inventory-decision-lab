# Deep Dive Plan

Target length: 30 minutes.

## Agenda

| Minutes | Topic | Evidence |
|---:|---|---|
| 0-3 | Problem framing and cost function | `README.md` |
| 3-7 | Source contracts and feature timing | `src/perishable_lab/data/contracts.py`, `src/perishable_lab/feature_store.py` |
| 7-12 | Forecast model, calibration, and interval metrics | `docs/MODEL_CARD.md`, `reports/example_run/forecast_metrics.json` |
| 12-18 | Perishable simulator and ordering policies | `docs/SIMULATOR_CARD.md`, `docs/POLICY_CARD.md` |
| 18-22 | Failure modes: stockouts, record noise, service floors | `docs/FAILURE_ANALYSIS.md`, `docs/issues` |
| 22-26 | Publication, monitoring, rollback, and batch orchestration | `docs/SYSTEM_CARD.md`, `gcp/DEPLOYMENT_RUNBOOK.md` |
| 26-30 | Limitations, next validation phase, and questions | `docs/FINAL_RELEASE_AUDIT.md` |

## Questions to invite

- How would the service-level target be chosen for different categories?
- Which costs need stakeholder sign-off before policy selection?
- Which segments should be calibrated separately once retailer data is available?
- What operational failure would block recommendation publication?
- Which batch artifact would you inspect first during rollback?
