# Historical survival without inspecting the target lot

The [destructive-plan study](INSPECTION_PLAN_VALUE.md) found that its fixed
sampling plans lost value against no-inspection sales. A separate alternative
is to learn from an existing archive and retain all fruit in each new lot.
This extension fits stratum curves once on historical lots and evaluates their
sale decisions on independent target lots without updating those curves.

## Historical data contract and model

[historical_baseline.R](R/historical_baseline.R) accepts:

| Field | Meaning |
|---|---|
| `lot_id` | Nonempty historical lot identifier |
| `harvest_day` | Whole calendar day of harvest, constant within a lot |
| `cohort` | Initial maturity stratum shared with deployment inventory |
| `day` | Positive whole fruit age at inspection |
| `n_checked` | Positive whole count inspected |
| `n_acceptable` | Reported acceptable count from zero to `n_checked` |

The archive needs at least two distinct lots, unique lot/stratum/age rows and
coverage of all eligible strata within each lot. Observation availability is
`harvest_day + day <= fit_calendar_day`. Thus a historical age-24 observation
can inform a new lot's age-12 decision when it occurred earlier on the calendar.
Unavailable observations are rejected rather than silently removed.

Counts are summed within each stratum/age, then the existing binomial fitter
estimates one Weibull curve per stratum with externally fixed grading accuracy:

\[
 q_g(t)=\mathrm{Se}\,S_g(t)+(1-\mathrm{Sp})(1-S_g(t)).
\]

This is a **working marginal model**, not a hierarchical fit or a particular
target lot's latent survival curve. A mixture of lot-specific Weibulls need not
be Weibull. Equal historical sample sizes give equal lot weight at each age;
unequal plans instead weight the fit by checked-fruit counts. No model-based
standard errors are inferred from treating all historical fruit as independent
replications of the same lot. The reported negative log likelihood belongs to
the aggregated working model, not a cross-study model-selection comparison.

The frozen model retains training IDs, the calendar cutoff, aggregated counts,
fitted parameters and grading assumptions. Application rejects a training lot
ID and rejects a model fitted after the target decision calendar date. These
checks rely on truthful source identifiers and availability dates.

## Use

From `studies/orange_storage_decision`, this example uses the saved synthetic
archive; its counts are not field observations:

```r
source("R/model.R")
source("R/sampling.R")
source("R/historical_baseline.R")
history <- read.csv("results/historical_baseline/history.csv")
inventory <- data.frame(cohort = c("advanced", "intermediate"),
  mass_kg = c(350, 500), initially_sellable = TRUE, shape = 1, scale = 1)
model <- fit_historical_survival(history, inventory, fit_calendar_day = 0,
  sensitivity = 0.9, specificity = 0.9)
prices <- expand.grid(cohort = inventory$cohort, day = 12:28,
                      stringsAsFactors = FALSE)
prices$price_eur_per_kg <- 0.8
historical_sale_decision(model, "new-lot", inventory, prices,
  harvest_day = 0, decision_day = 12)
```

Target metadata supplies initial masses and stratum membership. Shape/scale
placeholders are replaced by the historical fits. Sale-day prices, a two-day
delivery lag and future eligible holding cost determine the selected date;
the earliest maximum wins. No target inspection counts enter this policy.

## Prespecified experiment

[historical_evaluation.R](R/historical_evaluation.R) creates 100 historical lots
with the original nearby-shape generator (advanced/intermediate shape centres
2.2/1.8 and scale centres 18/36, with the existing lognormal variation). Each
has 60 checks per stratum at ages 4/8/12/16/20/24, totalling 72,000 reported
checks. Known sensitivity and specificity are both 0.90. Harvest dates ensure
all counts are available before calendar day zero, when the model is frozen.

Then generate 200 independent target lots from the same regime. Each has 850 kg
of eligible fruit at 0.20 kg per fruit; stratum masses are rounded accordingly.
The 150 kg immature stratum remains excluded from fresh-market returns and
eligible holding costs. Target harvest is calendar day zero, decisions occur
at fruit age 12, and candidate sale days are 12--28. All historical-policy
dates are fixed using only metadata and the hypothetical known price path
before generating any target fruit lifetimes.

Compare with no-inspection sales fixed at days 12 and 16, and the existing
AIC-mixture policy using 30 or 180 destructive checks per stratum on ages
3/6/9/12. Inspection plans have nested random samples without repeated fruit;
they lose 48 or 288 kg and pay EUR 0.02 per check. All alternatives use the same
finite fruit population per target lot, excluding exactly those fruit destroyed
under an inspection plan. All returns include eligible holding from harvest
through delivery at EUR 0.001/kg/day, including early-removal storage savings.

The archive is assumed already available. Its collection labour, destroyed
fruit, storage and model-development costs are excluded. The study evaluates
deployment conditional on that archive, and does not establish that collecting
it would pay for itself. Comparisons with destructive plans combine differences
in decisions, information and physical sampling cost; they do not establish
superior predictive accuracy over the per-lot models.

## Evaluation and saved findings

Paired target-lot return differences use 1,000 whole-lot percentile bootstrap
resamples and marginal 95% intervals. Strict downside frequencies use all
target lots. The archive remains fixed: these intervals measure target-lot
variation conditional on one trained model, not uncertainty across training
archives or model-selection procedures. No method was tuned on target outcomes.

Future assessments at ages 16/20/24 use true acceptable states on the full
uninspected population. Individual-fruit Brier and log-loss scores are
standardised by initial eligible mass. Predicted-minus-observed mass measures
aggregate inventory bias; this is not stratum-level calibration. Repeated future
assessments of the same fruit are never treated as independent bootstrap units.

The [saved report](results/historical_baseline/RESULTS.md) shows:

| Comparator | Historical-policy gain EUR/lot | 95% interval | Historical policy worse |
|---|---:|---:|---:|
| No inspection, day 12 | 20.31 | [15.10, 26.51] | 8.0% |
| No inspection, day 16 | 38.96 | [33.43, 44.55] | 12.5% |
| Destructive, 30 checks/stratum/day | 64.55 | [57.09, 72.75] | 1.0% |
| Destructive, 180 checks/stratum/day | 197.80 | [193.83, 202.10] | 0.0% |

Mean historical-policy return is EUR 495.44, with mean sale day 14.66.
Positive returns coexist with overprediction of acceptable mass: mean biases
are +6.84, +7.95 and +6.56 kg at ages 16, 20 and 24, respectively, with all three
marginal intervals above zero. These targets must not be reused to correct the
model and then report the correction as an independent test result.

The generator, grading accuracy and prices are assumed known and stable across
history and deployment. Distribution shifts, dependence, mass-related failure,
handling damage, archive-acquisition economics and empirical validation remain
open. The findings are synthetic evidence for this comparison, not field claims.

## Reproduction

```sh
Rscript tests/test_historical_baseline.R
Rscript scripts/run_historical_baseline.R 200
```

The optional second argument is the output directory. Seeds fixed before the
full run are `20261113` (archive), `20261114` (target metadata/prices), `20261115`
(target fruit), `20261116` (inspection sampling), and `9216` (bootstrap).
Saved settings record R version and RNG kind. Historical counts, frozen fits,
target returns, future measurements, both summaries and the figure are saved.
Tests rebuild the fits and summaries and check calendar availability, lot-ID
separation, fixed decisions before outcomes and analytical proper scores.
