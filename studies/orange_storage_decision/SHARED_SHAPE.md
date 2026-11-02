# A shared survival shape with stratum-specific deterioration scales

Short, noisy inspection histories can produce unstable estimates when every
stratum has its own Weibull shape and scale. The new model estimates a common
shape from all strata while retaining separate scale parameters. This reduces
the number of parameters, but adds an assumption that must be tested.

## Model and API

For eligible stratum `g`,

\[
S_g(t)=\exp\{-(t/\lambda_g)^k\},\qquad
q_g(t)=Se\,S_g(t)+(1-Sp)\{1-S_g(t)\}.
\]

`fit_shared_shape_weibull()` maximises the sum of aggregated binomial
log-likelihoods for reported counts with probabilities `q_g(t)`. It estimates
one common positive `k` and one positive `lambda_g` per stratum: `G+1`
parameters instead of the separate model's `2G`. A common shape does **not**
imply equal survival probabilities; strata with different scales retain
different deterioration curves.

Each row contributes its actual inspection sample size. This is a joint
likelihood for stratum-conditional curves, without the inventory weighting
used by the deliberately unstratified pooled baseline. Inventory mass enters
predicted mass, economic decisions and standardised held-out scoring.

```r
source("R/model.R")
source("R/sampling.R")
source("R/shared_shape.R")
fits <- fit_shared_shape_weibull(inspections, cohorts,
                                 sensitivity = 0.9, specificity = 0.9)
fitted <- with_fitted_survival(cohorts, fits)
decision <- optimal_batch_sale(fitted, prices,
                                storage_eur_per_kg_day = 0.001,
                                decision_day = 12, delivery_lag_days = 2)
```

Returned rows contain `cohort`, the common `shape`, each stratum's `scale`,
and its `negative_log_likelihood` contribution. They work with the existing
inventory and decision functions. Initial inventory survival parameters do
not influence the fit. Sensitivity and specificity default to one; supplied
rates are treated as fixed. For one eligible stratum the function delegates
to the existing fitter, since the two models coincide.

The joint optimiser compares converged solutions from three deterministic
starting points. Bounded L-BFGS-B attempts fall back to PORT on failure; a
finite objective alone is not accepted as convergence. Numerical bounds match
the separate fitter: shape 0.25-10, with each scale between that stratum's
earliest inspection/100 and latest inspection*100. These are safeguards, not
validated biological constraints or a proof of a global optimum. Reordering
input rows or inventory strata does not alter the fit. Existing fitters and
their bootstrap APIs are unchanged; they do not automatically use this model.

## Prespecified comparison

Use 200 independent synthetic lots, with the same base mass, scale variation
and hypothetical price generator as the previous studies. Initially eligible
mass totals 850 kg; 150 kg of immature inventory contributes no revenue.
The two original independent log-normal shape multipliers `u` and `v` have
log standard deviation 0.08. They are coupled across three generating regimes:

| Regime | Advanced shape | Intermediate shape |
|---|---|---|
| Common shape | `2*sqrt(u*v)` | `2*sqrt(u*v)` |
| Nearby shapes | `2.2*u` | `1.8*v` |
| Different shapes | `1.0*u` | `3.5*v` |

The equal-shape regime satisfies the restriction. The nearby regime retains
the original heterogeneous shape generator. The different-shape regime tests
the cost of imposing a false restriction; it is not omitted if it performs
poorly. These are illustrative assumptions, not estimates from orange data.

1. With seed `20261102`, draw lot inventory, price paths and independent
   uniforms for reported inspections on days 3/6/9/12 (180 per stratum/day).
   Map the same uniforms through binomial inverse CDFs in every regime.
   Inspection sensitivity and specificity are both 0.9 and are known to both
   models. Neither model sees true counts or true survival parameters.
2. Fit both models and choose dates in days 12-28. Delivery takes two days;
   holding costs EUR 0.001 per initial eligible kg per day. There is no model
   selection based on later scores. All lots' decisions are fixed first.
3. Only then, with seed `20261103`, draw future uniforms. Transform them into
   gold-standard inspections at days 16/20/24 (250 per stratum/day) and fruit
   failure times under each regime. Both models share identical outcomes;
   regimes share uniforms, without forcing their distinct outcomes to match.
4. Score inventory-standardised Brier/log loss and realised net sale returns.
   Compare shared versus separate fits and immediate sale. Bootstrap paired
   whole-lot mean differences 1,000 times with seed `9211`. Intervals are
   marginal without multiplicity adjustment; downside fractions exclude ties.

Changing the future-outcome seed cannot change fitted shapes or sale dates.
Reordering or subsetting regimes preserves each retained lot's measurements.
Training/fitting failures abort with lot and scenario context; difficult lots
are not silently discarded. Each scenario has 200 independent lots, not 600
independent observations obtained by pooling the paired regimes.

## Reproduction and interpretation

```sh
Rscript tests/test_shared_shape.R
Rscript scripts/run_shared_shape.R
# Optional lot count and destination:
Rscript scripts/run_shared_shape.R 500 /tmp/orange-shared-shape
```

The [saved report](results/shared_shape/RESULTS.md) contains the paired records,
estimated and generating shapes, summary, settings and a figure. Prediction
and economic effects are reported separately; improvements are not presumed.

In this saved run, shared shape improves average Brier and log loss in all
three regimes. Mean returns improve by EUR 9.81 and EUR 9.82 per lot for equal
and nearby shapes. With strongly different shapes, the mean return difference
is EUR 3.97 with a 95% interval of [-4.29, 12.10], while observed underperformance
against immediate sale rises from 21.5% to 29.5% of lots. Better mean prediction
scores therefore do not establish a superior decision in every regime.

This experiment assumes correct Weibull deterioration within each stratum,
independent inspection samples, exact calibration, known prices and negligible
inspection removals. It does not combine the finite-calibration bootstrap or
post-cutoff hazard shifts with the new model. Sharing shape can reduce
variation while introducing systematic extrapolation error. Real use needs
independent-lot model comparison and calibration under [PROTOCOL.md](PROTOCOL.md),
not selection of whichever model wins a synthetic scenario.
