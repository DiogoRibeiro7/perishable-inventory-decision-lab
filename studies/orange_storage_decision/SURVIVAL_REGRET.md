# Minimax regret when target shelf life is uncertain

The [historical shift study](HISTORICAL_SHIFT.md) found that shorter target
lifetimes can reverse the historical policy's advantage over day-12 sale.
This extension asks whether minimax regret over a fixed set of shelf-life
scenarios improves deployment decisions. It uses fresh historical archives and
targets; the earlier study motivates the question, but supplies no evaluation
observations to this experiment.

The [saved results](results/survival_regret/RESULTS.md) retain a negative finding:
at 25% shorter lifetimes, the new rule earns EUR 0.82 less per lot than the
historical rule (95% interval: -0.97 to -0.65). Its mean advantage over day-12
sale is EUR -6.88, versus -6.06 for the historical policy. At 25% longer
lifetimes it gains EUR 0.77 over the historical policy [0.63, 0.90]. Minimising
worst fitted regret does not resolve the shorter-life failure in this study.

## Decision rule

Fit the existing stratum-specific historical model using completed lots only.
For each declared multiplier m, multiply both eligible Weibull scales by m,
keeping shape, initial masses and the supplied price path fixed. Compute
fitted expected net return V(m,d) for each available sale date d.

```text
regret(m,d) = max over candidate dates t of V(m,t) - V(m,d)
chosen date = earliest d minimising max over declared m of regret(m,d)
```

The decision set is `{0.75, 1, 1.25}`. No probabilities are assigned to these
scenarios. Each scenario has its own fitted best date, rather than a hindsight
optimum from realised fruit outcomes. The rule differs from maximising worst
expected profit or imposing a bound on losses against immediate sale.

The new rule and the existing price-scenario policy share
`minimax_regret_grids()`. This calculation accepts aligned expected-value grids
and returns the chosen date, all-date worst-regret values and scenario-level
values/regrets. Existing price-policy constraints and tests remain in place.
With only the multiplier 1, the survival rule reduces to ordinary fitted
expected-value optimisation. Exact ties select the earliest date.

Historical models retain lot-ID and calendar availability checks. The public
policy accepts fitted curves and initial metadata, without target true survival
parameters, fruit lifetimes or a realised shift indicator. All decisions use
only pre-outcome information.

## Fixed prospective evaluation

Before this experiment's target scoring, specify 30 independent repetitions,
100 historical lots and 50 fresh target lots per repetition, master seed
20261119, bootstrap seed 9219 and 2,000 resamples. Historical inspection ages
are 4/8/12/16/20/24, with 60 checks per stratum/age/lot and known grading
sensitivity/specificity of 0.90. Each archive has 72,000 reported checks.

Within each repetition, freeze the historical model and both policies' sale
dates before generating any target fruit outcomes. Evaluate lifetime factors
`{0.60, 0.75, 1, 1.25, 1.40}` on the same fruit identities and prices.
The factors 0.60 and 1.40 lie beyond the decision set. Each factor scales
lifetimes from target harvest, equally across both eligible strata; historical
data and target Weibull shapes stay unchanged.

Both policies and fixed day-12 sale retain all 850 kg of eligible target fruit.
No target inspections occur. Realised returns include holding from harvest
through delivery at EUR 0.001/kg/day, with a two-day delivery lag. The common
holding cost incurred before day 12 cancels from fitted regret. Initially
immature fruit remain outside eligible revenue and holding costs. Historical
archive acquisition, destructive sampling, labour and development costs are
excluded.

Report three paired return contrasts and three strict-loss frequencies for
each evaluation factor. Do not average scenarios into an overall ranking:
there is no shift-frequency model. Ties count as neither losses nor gains in
the strict-loss indicators.

Average targets within each repetition/scenario, then bootstrap entire
independent repetitions using common indices across metrics and scenarios.
The independent sample size is 30, not the 7,500 target/scenario records.
Intervals include both archive and finite-target-panel variation and describe
expected performance of the training/deployment procedure. They are marginal
percentile 95% intervals without multiplicity adjustment, not prediction
intervals for individual lots. Failed repetitions stop the run.

## Reproduction and API

Run from `studies/orange_storage_decision`, using base R:

```bash
Rscript scripts/run_survival_regret.R
Rscript tests/test_survival_regret.R
Rscript scripts/run_survival_regret.R 3 /tmp/orange-survival-regret-smoke 10
```

The script accepts repetitions, output directory and targets per repetition.
The API exposes the decision and evaluation sets separately:

```r
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/robust_policy.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")
source("R/survival_regret.R")
study <- run_survival_regret_experiment(n_repeats = 3, n_targets = 4,
  n_history = 4, decision_multipliers = c(0.75, 1, 1.25),
  evaluation_multipliers = c(0.6, 0.75, 1, 1.25, 1.4), master_seed = 44)
set.seed(9219)
estimates <- summarize_survival_regret(study$records, n_boot = 200)
estimates$summary
```

The [report](results/survival_regret/RESULTS.md) links the seed manifest,
aggregate historical counts, fits, target measurements, repetition means,
intervals and settings. Tests reconstruct every saved fit and summary, and
regenerate a complete target panel. Fitted regret allows an absolute numerical
difference below EUR 0.0001 across R builds; realised outcomes retain tighter
checks. Analytical examples verify scale transformations, lag/cost accounting,
ties and the single-scenario limit. Tests also enforce the information cutoff
and reject incomplete pairs or inconsistent return accounting.

## Interpretation

Mean sale day moves from 14.25 to 14.34, with dates changing on 10.5% of lots.
Mean worst fitted regret decreases from EUR 11.41 to 11.02, as expected from
the optimisation criterion. But the rule sells slightly later on average and
performs worse in the shorter-lived scenarios. Regret measures forgone
opportunity in each fitted world; reducing it can trade greater exposure to
early deterioration for gains when fruit lasts longer.

This is a finite-model criterion, not a guarantee of safer realised returns,
better survival forecasts or a bound for every multiplier between the chosen
values. Heterogeneous target lots do not exactly follow the fitted marginal
Weibull curve. Scenario misspecification and parameter uncertainty remain,
despite the repeated-archive evaluation. Prices and grading accuracy are
assumed known; empirical validation, shift probabilities, adaptation and
historical-data economics remain open. The negative result is preserved
without retuning the decision set on these targets.
