# Research-Track Model Card

## Scope

This card covers the two research-track candidates in `src/perishable_lab/forecasting/research.py`:

- `NegativeBinomialQuantileForecaster`
- `ResidualScenarioEnsembleForecaster`

Both produce the same non-negative monotone quantile columns as the existing baseline.

## Intended Use

Use these models for offline research comparisons after the robust baseline has run. They are not default production models.

## Evidence Required Before Use

Before promotion beyond offline research, a candidate must show:

- reproducible paired operating-cost improvement;
- acceptable calibration and tail performance;
- stable training and prediction time;
- deterministic serialization plan;
- segmented monitoring and fallback to the baseline;
- no degradation on cold-start or shifted cohorts.

## Limitations

The negative-binomial candidate assumes a count distribution family that may misrepresent promotion periods, censored demand, or structural breaks. The residual scenario ensemble assumes historical residuals remain exchangeable enough to reuse. Neither candidate fixes missing inventory, late data, product identity issues, or shelf-life misspecification.

## Current Decision

Default decision: reject for deployment until an experiment manifest and paired policy table show operational improvement with uncertainty bounds. Keep candidates only for offline comparison and shadow-style evaluation.
