# Claims Audit

Unsupported commercial-impact language was excluded. The case study uses synthetic results only as software and scenario evidence.

| Claim | Evidence | Status |
| --- | --- | --- |
| Forecasting is only one input to an ordering decision. | `docs/ARCHITECTURE.md`; `docs/FORECAST_DECISION_CONTRACT.md`; `tests/test_decision.py` | Supported |
| Product identity, censored sales, inventory error, shelf life, and supplier uncertainty are represented as explicit concerns. | `tests/test_product_identity.py`; `tests/test_demand_censoring.py`; `tests/test_inventory_reconciliation.py`; `tests/test_shelf_life.py`; `tests/test_supplier.py` | Supported |
| The simulator is verified for software invariants but not validated as real retailer process evidence. | `docs/SIMULATOR_VV_REPORT.md`; `tests/test_simulator_vv.py`; `tests/test_properties.py` | Supported |
| A better forecast metric can still produce a worse order. | `docs/ARCHITECTURE.md`; `src/perishable_lab/evaluation/reporting.py`; `tests/test_dashboard.py`; explicit failure analysis in `docs/PORTFOLIO_CASE_STUDY.md` | Supported |
| Publication prevents store-facing readers from observing partial batches. | `src/perishable_lab/publication.py`; `tests/test_publication.py`; `docs/PUBLICATION_RUNBOOK.md` | Supported |
| The committed example run proves commercial lift. | No evidence; explicitly not claimed. | Removed |
| Security roles separate approval and publication. | `docs/IAM_MATRIX.md`; `src/perishable_lab/security.py`; `tests/test_security.py` | Supported |
| Store-operations enhancements must tie to workflow evidence. | `src/perishable_lab/discovery.py`; `tests/test_discovery.py`; `docs/STORE_DISCOVERY_GUIDE.md` | Supported |
