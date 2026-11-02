# Uncertainty from finite inspection calibration

The [inspection-error likelihood](INSPECTION_ERROR.md) conditions on supplied
sensitivity and specificity. In practice, those rates may be estimated from a
finite reference sample. This extension accepts independent reference confusion
counts and compares two parametric bootstraps: one holds the estimated rates
fixed; the other resamples both reference counts and storage inspections.

## Reference data contract

Positive means commercially acceptable under the reference standard. Each row
of `calibration` contains these nonnegative whole-number fields:

| Field | Meaning |
|---|---|
| `day` | Day reference outcomes became available, no later than the decision |
| `true_positive` | Truly acceptable fruit labeled acceptable |
| `false_negative` | Truly acceptable fruit labeled unacceptable |
| `true_negative` | Truly unacceptable fruit labeled unacceptable |
| `false_positive` | Truly unacceptable fruit labeled acceptable |

Reference labels are assumed correct. Each true class must have a positive
total count. Observations must come from an independent calibration sample,
not from the storage inspection labels being fitted. This independence and
reference accuracy are provenance requirements, not properties the table
validator can establish. Rates are assumed stable across strata, days and
reference/storage populations. Rows are pooled by **counts**, not by averaging
row-wise rates; the two true-class sample sizes may differ.

`inspection_calibration_rates(calibration, decision_day)` returns
`sensitivity = TP/(TP+FN)` and `specificity = TN/(TN+FP)`, along with their
reference sample sizes. As in the existing model, their sum must exceed one.
Reference observations after the decision cutoff are rejected.

```r
source("R/model.R")
source("R/sampling.R")
source("R/calibration.R")
calibration <- data.frame(day = 10, true_positive = 45, false_negative = 5,
                          true_negative = 45, false_positive = 5)
set.seed(20261101)
result <- bootstrap_calibrated_sale(
  inspections, cohorts, prices, calibration,
  storage_eur_per_kg_day = 0.001, decision_day = 12,
  delivery_lag_days = 2, prediction_day = 20, n_boot = 500)
summarize_calibration_bootstrap(result$draws)
```

The point estimate fits the reported inspection counts using the estimated
rates. Only inspections available by the decision day can enter. Initial
inventory shapes/scales do not supply hidden survival information to fitting.

## Two independent samples in each replicate

Let the original estimates be `Se_hat`, `Sp_hat`, and fitted survival `S_hat`.
The original fitted reported-label probability is
`q_hat = Se_hat*S_hat + (1-Sp_hat)*(1-S_hat)`.

1. Draw new reported inspection counts `Y* ~ Binomial(n, q_hat)`.
2. Independently draw reference counts `TP* ~ Binomial(N_positive, Se_hat)`
   and `TN* ~ Binomial(N_negative, Sp_hat)`, then re-estimate `Se*` and `Sp*`.
3. Fit a conditional model to `Y*` with the **original** rates, and a
   recalibrated model to the **same Y*** with the resampled rates.
4. For each refit, recompute the sale date and expected acceptable mass at the
   fixed future prediction day. Initially immature mass is always excluded.

Training counts must **not** be generated from `Se*` and `Sp*`: doing that
would couple the independent samples and change the uncertainty being
estimated. All random draws are generated before refits; a failed fit cannot
shift later random draws. The caller controls the RNG seed.

One draw row is returned for every iteration and method. `status` distinguishes
`success`, `uninformative_calibration` (`Se* + Sp* <= 1`), and `fit_failure`.
Failures have missing decision/mass values and an explanatory `detail`.
They are never replaced by repeated draws. Summaries report all attempts and
failure counts. Percentiles use successful refits only, which can be selective
if failures are substantial; an all-failed method has missing percentiles.

Sale-day percentiles use empirical order statistics, preserving integer days.
Mass percentiles use R's default type-7 interpolation. These are bootstrap
distributions of a two-stage estimator, not posterior probabilities or
validated confidence sets for the optimal day. Mass summaries describe
uncertainty in **expected** acceptable mass, excluding future fruit-outcome
variation. They do not quantify realised revenue or price risk.

## Reproducible illustration

The [saved example](results/calibration_uncertainty/RESULTS.md) uses one
synthetic 850-kg eligible lot, two Weibull strata and independent reported
inspections on days 3/6/9/12 (180 per stratum/day). A separate 150-kg immature
stratum contributes no revenue or predicted acceptable mass. The price path
is a hypothetical EUR 0.80/kg on day 12 plus EUR 0.04/kg per later day.

The three constructed calibration tables have 50, 200 or 1,000 fruit **in each
true class**, with exactly 90% sensitivity and specificity. They deliberately
hold rates fixed while varying reference precision. They are not randomly
drawn calibration datasets and do not constitute a repeated-sampling coverage
study. Training seed `20261031` and bootstrap seed `20261101` are fixed before
running the illustration; 500 draws per method and reference size are saved.

The bootstrap seed is reset for each reference size. Hence all three cases
have identical point fits and conditional draws; their recalibrated fits use
the same training draws and shared independent reference uniforms. All input
tables, generating truth, settings and attempted draws are saved for audit.

In this example, the day-20 mass range is 52.5-498.0 kg when calibration is
held fixed, versus 0.2-528.5 kg when re-estimated from 50 reference fruit per
class. At 1,000 per class, the recalibrated range is 28.5-486.8 kg. All sale-day
ranges span days 12-28, the entire candidate window; the example therefore
retains substantial uncertainty even at the largest reference size. There
were no failed attempts in these saved draws.

```sh
Rscript tests/test_calibration.R
Rscript scripts/run_calibration_uncertainty.R
# Optional replicate count and destination:
Rscript scripts/run_calibration_uncertainty.R 1000 /tmp/orange-calibration
```

## Limits

This method propagates finite reference-sample variation under independent
binomial sampling. It does not address incorrect reference labels, rate drift,
common operator errors, nonrepresentative reference populations, model
misspecification, price uncertainty or correlation with storage inspections.

A plug-in binomial bootstrap has zero variation for a reference rate estimated
as zero or one. The API preserves that mathematical behavior; a finite sample
with no mistakes does **not** prove perfect accuracy. Boundary cases require a
different uncertainty method before operational interpretation. Finite
reference samples, weak identification of survival, and optimizer boundaries
also mean that nominal percentile ranges need not have nominal coverage.

Larger calibration samples need not narrow every estimated range in a finite
run. Empirical calibration and coverage across independent harvest lots remain
required by [PROTOCOL.md](PROTOCOL.md). This example is a methodological
demonstration, not evidence of operational profitability.
