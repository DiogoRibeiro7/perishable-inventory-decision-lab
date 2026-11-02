# Does a historical policy survive a change in shelf life?

The [historical baseline](HISTORICAL_BASELINE.md) and
[archive-uncertainty study](ARCHIVE_UNCERTAINTY.md) train and test under one
synthetic generating regime. This extension changes target shelf life while
keeping historical data, fitted curves and target decisions fixed. It measures
how a historical policy behaves when the target deterioration process differs
from the training process and the policy has no information about that change.

In the [saved study](results/historical_shift/RESULTS.md), a 25% reduction in
target fruit lifetimes reverses the advantage over fixed day-12 sale:
EUR +18.50 per lot in the unchanged scenario becomes EUR -4.86 (95% interval:
-5.95 to -3.85). The paired change is EUR -23.36 [-25.19, -21.59]. Mean day-20
inventory bias rises from -0.25 kg to +137.81 kg. A policy that works under the
historical regime can therefore lose money relative to immediate sale under
this declared shift. This is synthetic sensitivity evidence, not a measured
field effect or a forecast that such a shift will happen.

## Prespecified design

The study fixes 30 independent repetitions, 100 historical lots and 50 new
target lots per repetition, lifetime multipliers 0.75/1/1.25, master seed
20261118, bootstrap seed 9218 and 2,000 resamples before evaluating outcomes.
Every repetition has an independent historical archive and target panel;
scenarios within a repetition share the same fruit identities, masses and prices.

1. Generate historical inspections at ages 4/8/12/16/20/24, with 60 reported
   checks per stratum/age/lot and known sensitivity/specificity of 0.90. All
   historical observations precede calendar day zero. Fit one working marginal
   Weibull curve per initially eligible stratum before generating target lots.
2. Generate target grade masses and supplied price paths. Use only these public
   inputs and the frozen historical curves to choose sale dates from days
   12 through 28. All dates and forecasts precede every target fruit outcome.
3. Draw one finite population of target fruit lifetimes. For each multiplier m,
   set every fruit's lifetime to m times its original lifetime, preserving fruit
   identity. The policy receives neither m nor any target inspection outcomes.
4. Evaluate the historical date and fixed dates 12/16 against the same shifted
   fruit. Assess forecast mass, Brier score and log loss at ages 16/20/24.
   No target lot or adverse scenario is discarded, and fit failures stop the run.

The shift acts **from target harvest**, while history is unchanged. For a
target stratum with baseline Weibull shape k and scale lambda,

```text
T(m) = m * T(1)
S(t | m) = exp(-(t / (m * lambda))^k)
```

Thus 0.75 means 25% shorter lifetimes and 1.25 means 25% longer lifetimes.
Shapes remain unchanged. A common lifetime multiplier is not a common hazard
multiplier across strata with different shapes. This differs from the existing
[post-cutoff hazard stress](SURVIVAL_STRESS.md), which changes deterioration
after the decision cutoff for policies fitted from current-lot inspections.

## Outcomes and uncertainty

Every policy retains all 850 kg of initially eligible target fruit. Net returns
include holding from harvest through delivery at EUR 0.001/kg/day, with a
two-day delivery lag. Initially immature stock stays outside eligible revenue
and holding costs. There are no target inspections, and archive acquisition,
destructive sampling, labour and development costs are excluded.

Fixed-date returns change under a shift too. Report both the historical policy's
absolute return and its paired advantage over each fixed-date benchmark.
The fraction below day 12 counts strict losses; ties are not losses.

Forecasts concern true acceptance, not noisy grading labels. Brier/log loss
use individual-fruit outcomes weighted by initial stratum mass and average
equally over the three future days. Inventory bias is predicted minus observed
acceptable kg, separately by day. Scores change with acceptance prevalence and
outcome uncertainty as well as predictive error, so their change alone is not
a calibration diagnosis. Aggregate inventory bias is also not a complete
stratum-level calibration assessment.

First average target measurements within each repetition/scenario, then
bootstrap whole repetitions. Use the same resampled repetition indices for
every metric and scenario. Shift-minus-unchanged contrasts use paired block
differences. The independent sample size is 30, not the 4,500 target/scenario
records or the repeated future measurements. Tests verify that duplicating
targets within each repetition does not narrow these intervals.

The percentile 95% intervals describe expected performance of the training and
deployment procedure under each fixed scenario. They include archive and
finite-target-panel variation without separating those variance components.
They do not predict an individual lot's outcome or estimate how often a shift
will occur. Intervals are marginal without multiplicity correction.

## Reproduction and API

Run from `studies/orange_storage_decision`, using base R:

```bash
Rscript scripts/run_historical_shift.R
Rscript tests/test_historical_shift.R
# Small report-generation smoke test outside committed results:
Rscript scripts/run_historical_shift.R 3 /tmp/orange-shift-smoke 10
```

The script accepts repetitions, output directory and targets per repetition.
It fixes the historical archive size at 100 and the three stated shifts. The
API supports other positive multipliers, including an unchanged value of 1:

```r
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")
study <- run_historical_shift_experiment(n_repeats = 3, n_targets = 4,
  n_history = 4, multipliers = c(0.75, 1, 1.25), master_seed = 43)
set.seed(9218)
estimates <- summarize_historical_shift(study$records, n_boot = 200)
estimates$contrasts
```

The [saved report](results/historical_shift/RESULTS.md) links aggregate training
counts, fitted curves, target/scenario measurements, repetition means, intervals,
paired contrasts and settings. The seed manifest regenerates full historical
archives and target panels through `run_historical_shift_replication()`. Counts
are sufficient for reconstructing the working fit; they are not individual
historical-lot data. Tests reconstruct every saved fit and interval, audit
coupled mass/return monotonicity, and regenerate one complete repetition.
Reconstruction requires identical IDs, scenarios and sale dates, with absolute
error at most 1e-10 in realised masses/returns. Fitted masses allow 0.0001 kg
and proper scores 1e-7 for numerical variation between R builds; saved-summary
reconstruction retains its existing tighter tolerance.

## Interpretation limits

In the longer-lifetime scenario, day-12 return advantage increases to EUR 40.68
while day-20 inventory bias becomes -105.25 kg. Stronger return performance
against one benchmark therefore does not establish accurate mass forecasts.

These shifts change both strata uniformly, without altering prices, shapes,
grading accuracy or initial mass. They do not cover covariate-dependent shifts,
mixture changes, dependence, changes in price or grading, or empirical storage
conditions. The analysis evaluates a fixed policy and does not test detection,
retraining, adaptation, or a shift-aware optimum. It cannot recommend a new
operational policy from these targets. Empirical validation and historical-data
economics remain open, and the project remains an unfeatured prototype.
