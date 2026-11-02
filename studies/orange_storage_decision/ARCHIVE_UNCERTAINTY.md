# How much does the historical training archive matter?

The [frozen historical baseline](HISTORICAL_BASELINE.md) estimates deployment
performance conditional on one archive. This extension repeats the entire
training-and-evaluation procedure. It measures expected performance when a new
historical archive and a new target panel are drawn from the same synthetic regime.
It does not estimate the economics of collecting historical data.

## Fixed design

Before evaluation, the study specifies 30 independent repetitions, historical
archive sizes of 10 and 100 lots, 50 target lots per repetition, master seed
20261117, bootstrap seed 9217 and 2,000 bootstrap resamples. These settings do
not use the previous study's target observations to tune a model or policy.

Within each repetition:

1. Generate 100 historical lots, each with six fruit ages (4/8/12/16/20/24 days),
   two strata and 60 reported checks per stratum/age. Use the first 10 lots as
   the smaller nested archive. Known sensitivity and specificity are both 0.90.
2. Fit the same working marginal Weibull model separately to each archive.
   All observations precede calendar day zero. Freeze both models before
   generating any target metadata or fruit outcomes.
3. Generate 50 new lots and supplied price paths. Only initial grade masses and
   price paths reach the decision policies; true survival parameters do not.
   Fix every policy's sale date before generating target fruit lifetimes.
4. Evaluate both dates and fixed dates 12/16 on each lot's same finite fruit
   population and prices. Keep all 850 kg of eligible target fruit, with no
   target inspections. Include holding costs from harvest through delivery at
   EUR 0.001/kg/day and a two-day delivery lag.
5. Score future true acceptance at days 16/20/24. Brier and log loss are
   individual-fruit proper scores weighted by initial stratum mass, then
   averaged equally over the three future days. Bias is predicted minus
   observed acceptable kg, separately for each future day.

Histories and target panels are disjoint across repetitions. The paired designs
within a repetition intentionally share data: nested historical archives and
identical target outcomes reduce noise in the archive-size comparison. A seed
manifest fixes distinct history, target-metadata and fruit-outcome seeds for
every repetition before fitting. No failed repetition is dropped or retried
with another seed; failures stop the study with the repetition number.

## Estimand and uncertainty

For archive size n, let D(r,n) be the training data in repetition r and Y(r,i)
the i-th target lot. The reported mean gain over day 12 is

```text
mean over r { mean over i [ return(policy fitted on D(r,n), Y(r,i))
                           - return(day 12, Y(r,i)) ] }
```

First average targets within each repetition and archive size. Bootstrap the
30 independent repetition means with replacement, preserving the two sizes as
a pair. The large-minus-small contrast uses differences of paired repetition
means, never a subtraction of separately estimated interval endpoints.
The same approach applies to prediction scores and inventory bias.

The 95% percentile intervals describe uncertainty in **expected performance of
the training-and-deployment procedure** under this generator. They include
variation from both archives and finite target panels. They are not prediction
intervals for the next archive or lot, nor confidence intervals conditional on
one deployed model. The saved standard deviations likewise mix archive and
test-panel variation; no variance-component decomposition is claimed.

The independent sample size is 30, even though there are 1,500 target lots and
3,000 policy/target records. Repeated future days and fruit from the same lot
add no independent training archives. Tests verify that duplicating all target
records with new within-panel IDs leaves the reported confidence intervals
unchanged. Intervals are marginal, without multiplicity adjustment.

## Reproduction and API

Run from `studies/orange_storage_decision`, using base R:

```bash
Rscript scripts/run_archive_uncertainty.R
Rscript tests/test_archive_uncertainty.R
# Smaller report-generation smoke test, written outside committed results:
Rscript scripts/run_archive_uncertainty.R 3 /tmp/orange-archive-smoke 10
```

The script takes repetitions, destination and targets per repetition, in that
order. The two archive sizes stay fixed at 10/100 in the report script. The API
also supports two other increasing sizes (at least two historical lots each):

```r
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
study <- run_archive_experiment(n_repeats = 3, n_targets = 4,
  archive_sizes = c(2, 4), master_seed = 42)
set.seed(9217)
estimates <- summarize_archive_experiment(study$records, n_boot = 200)
estimates$comparisons
```

See the [committed results](results/archive_uncertainty/RESULTS.md). The seed
manifest reconstructs each full historical archive with
`simulate_historical_inspections(max(archive_sizes), history_seed)` and each
repetition with `run_archive_replication()`. Repetition prefixes make IDs unique;
the smaller archive always uses the first generated lots, before any scoring.
`counts.csv` contains aggregated training counts, sufficient for the fitted
working likelihood, rather than individual historical-lot rows. Tests reconstruct
every fit from these counts and every reported interval from target records.

## Interpretation limits

In the [saved run](results/archive_uncertainty/RESULTS.md), using 100 instead of
10 historical lots raises mean deployment return by EUR 1.00 per target lot
(paired 95% interval: 0.37 to 1.82). Mean Brier score decreases by 0.00095 and
log loss by 0.00234. Both archive sizes outperform fixed day-12 sale on average
under this generator. These are modest incremental gains; the narrower spread
of repetition-level inventory bias with 100 lots is descriptive and does not
isolate training variance from finite-test-panel variance.

The larger archive uses 72,000 reported checks versus 7,200 for the smaller one.
Archive acquisition, destructive sampling losses, labour and model-development
costs are excluded. A return advantage does not establish that collecting an
extra 90 historical lots pays for itself, or that either size is optimal.

The marginal Weibull model approximates a heterogeneous mixture of lot-specific
curves. Increasing archive size can reduce estimation noise without removing
misspecification or predicting a target lot's latent curve. A signed change in
bias is not necessarily an improvement; assess its distance from zero.

The historical and target generators share one stable regime, with known prices
and grading accuracy. This remains synthetic evidence. Distribution shift,
empirical learning curves, within-lot dependence, uncertain prices and uncertain
grading accuracy require separate evaluations. The previous fixed-archive
results remain conditional on their original archive and are not reinterpreted
as intervals across training archives.
