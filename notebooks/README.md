# Notebooks

The core logic deliberately lives in importable, tested Python modules. Notebooks should be thin analytical views over persisted artifacts.

Suggested notebooks:

1. `01_data_generating_process.ipynb` — inspect seasonality, promotions, intermittency, and shelf-life mix.
2. `02_forecast_calibration.ipynb` — reliability plots, quantile loss, interval width, and segmented coverage.
3. `03_policy_frontier.ipynb` — waste versus fill-rate frontier across service levels.
4. `04_failure_analysis.ipynb` — products and stores where statistical and operational metrics disagree.
