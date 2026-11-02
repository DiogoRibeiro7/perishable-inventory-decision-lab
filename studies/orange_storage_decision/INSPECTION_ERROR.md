# Learning survival from imperfect inspections

Reported inspection outcomes can contain both false accepts and false rejects.
Treating those labels as true commercial acceptance changes the survival fit
and can change the chosen sale date. This extension supports a binomial
measurement-error likelihood with **fixed, externally calibrated** inspection
sensitivity and specificity, and compares it with the existing naive fit.

## Observation model and API

Let `S(t)` be true acceptable-fruit probability, `Se` sensitivity
(`P(reported acceptable | truly acceptable)`), and `Sp` specificity
(`P(reported unacceptable | truly unacceptable)`). By conditioning on the
true state, the probability of a reported acceptable label is

\[
q(t)=Se\,S(t)+(1-Sp)\{1-S(t)\},\qquad Y_t\sim\mathrm{Binomial}(n_t,q(t)).
\]

The fitter estimates the Weibull parameters of **S**, using **q** inside the
likelihood. It does not invert observed proportions into corrected counts:
sampling noise can put an observed pass fraction above `Se`, where such an
inversion would exceed one. The count likelihood still handles that observation.

`estimate_weibull_binomial()`, `fit_weibull_by_cohort()`,
`fit_pooled_weibull()` and `bootstrap_sale_days()` accept `sensitivity` and
`specificity`. Defaults of one retain the original perfect-inspection model.
Both rates must be finite scalars in [0,1] with `Se + Sp > 1`, so labels are
informative in the stated orientation. Rates are shared across strata and
inspection days. Returned fitted curves describe true acceptance.

```r
fits <- fit_weibull_by_cohort(inspections, cohorts,
                             sensitivity = 0.90, specificity = 0.95)
fitted_inventory <- with_fitted_survival(cohorts, fits)
bootstrap <- bootstrap_sale_days(inspections, cohorts, prices,
                                 storage_eur_per_kg_day = 0.001,
                                 decision_day = 12, delivery_lag_days = 2,
                                 sensitivity = 0.90, specificity = 0.95)
```

Bootstrap counts are sampled from fitted **reported-label** probabilities,
and each refit uses the same fixed rates. This conditions on the external
calibration; it does not propagate uncertainty in sensitivity or specificity.
The separate [finite-calibration bootstrap](CALIBRATION.md) accepts reference
confusion counts and resamples both independent sources of observations.
The rates cannot simply be learned alongside survival from these same
aggregated labels without additional identifying information or assumptions.

## Prespecified synthetic comparison

Use 200 independent lots and four illustrative observation scenarios:

| Scenario | Sensitivity | Specificity |
|---|---:|---:|
| Perfect inspection | 1.00 | 1.00 |
| Balanced errors | 0.90 | 0.90 |
| More false accepts | 0.95 | 0.80 |
| More false rejects | 0.80 | 0.95 |

The corrected policy is given the actual generating rates, as an idealisation
of accurate external calibration. These are assumed settings, not estimates
from orange inspections. Both policies fit stratum-specific Weibull curves;
the naive fit assumes perfect labels. There is no tuning on future results.

1. Generate true inventory, clean training counts on days 3/6/9/12 (180 per
   stratum/day), and known price forecasts using seed `20261028`.
2. With seed `20261029`, couple classification errors across scenarios. Given
   a clean count K, draw true positives from Binomial(K, Se) and false
   positives from Binomial(n-K, 1-Sp), using shared uniform pairs and inverse
   CDFs. Their sum is the reported count. Marginally it follows Binomial(n,q).
   A perfect detector returns the original counts exactly.
3. Fit both policies from the same reported counts and initial mass/stratum
   metadata, then choose dates at day 12. Hidden survival parameters are
   replaced by placeholders before fitting; clean counts and future outcomes
   are not supplied to the policy. All scenarios' decisions are fixed first.
4. Only then draw gold-standard holdout inspections on days 16/20/24 (250 per
   stratum/day) and fruit failure times using seed `20261030`. These outcomes
   are shared across policies and inspection scenarios. Score true acceptance
   with inventory-standardised Brier and log loss, and evaluate realised net
   returns including holding costs and two-day delivery rejection.
5. Compare corrected minus naive returns and naive minus corrected prediction
   scores within each lot. Use 1,000 whole-lot bootstrap resamples per mean
   contrast, seed `9190`. Report immediate sale and descriptive downside too.

Intervals are marginal without multiplicity adjustment. Exact ties are not
counted as underperformance. Predictive improvements need not imply economic
improvements, and negative findings are retained. Changing the outcome seed
cannot affect fits or dates; changing label noise cannot affect fruit
outcomes or immediate-sale revenue. Scenario order/subsets preserve pairing.

## Reproduce

From `studies/orange_storage_decision`, using base R:

```sh
Rscript tests/test_inspection_error.R
Rscript scripts/run_inspection_error.R
# Optional lot count and destination:
Rscript scripts/run_inspection_error.R 500 /tmp/orange-inspection-error
```

The [saved report](results/inspection_error/RESULTS.md) includes 800 paired
records, summary statistics, settings and a figure. The old evaluation
retains its original output under default perfect-label parameters.

In this run, correction adds EUR 40.47-50.99 per lot relative to naive fitting
in the three noisy scenarios. However, all three corrected-minus-immediate
95% intervals include zero. Correction worsens mean future Brier scores in
the balanced-error and false-reject-heavy scenarios, and mean log loss in
all three. The comparison does not support a general prediction improvement
or an advantage over immediate sale under noisy inspections.

## Limits and empirical requirements

Before using correction on real data, independently estimate classification
rates against a credible reference standard and assess their stability across
grades, operators, days and storage conditions. This experiment assumes exact
rates, independent label errors, gold-standard future inspections, correct
Weibull deterioration, negligible inspection removals and known prices.
It does not validate performance under misspecified calibration, operator
dependence or the deterioration shifts in [SURVIVAL_STRESS.md](SURVIVAL_STRESS.md).
Parameter bootstraps conditional on fixed rates can understate total
uncertainty when calibration is estimated. Correction also cannot restore
information lost through misclassification: short, noisy training histories
can produce unstable extrapolations even with the correct likelihood. The
existing numerical bounds (shape 0.25-10, scale from earliest inspection/100
to latest inspection*100) remain in force; fitted estimates can reach them.
These bounds are numerical safeguards, not biologically validated constraints.
Synthetic findings are not field profitability claims;
[PROTOCOL.md](PROTOCOL.md) still governs empirical work.
