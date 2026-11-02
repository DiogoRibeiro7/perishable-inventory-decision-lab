# Averaging survival models before choosing a sale date

Separate and shared Weibull shapes trade flexibility against estimation
variation. This extension combines their predicted survival curves using
weights calculated entirely from inspections available at the decision
cutoff. It evaluates the resulting sale policy against both components and
immediate sale on fresh synthetic lots.

## Likelihood, weights and decisions

Both components fit the same reported binomial counts, with the same fixed
sensitivity and specificity and the same binomial constants. Each inspection
row contributes its actual sample size; inventory mass does not weight the
likelihood. With `G` eligible strata, the separate model estimates `2G`
parameters and the shared model estimates `G+1`. The externally fixed
inspection rates are not estimated parameters in either fit.

For component `m`, with negative log-likelihood `NLL_m` and parameter count
`p_m`, the rule is:

\[
AIC_m=2NLL_m+2p_m,\quad
\Delta_m=AIC_m-\min_j AIC_j,\quad
w_m=\frac{\exp(-\Delta_m/2)}{\sum_j\exp(-\Delta_j/2)}.
\]

The [R documentation for AIC](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/AIC.html)
defines the criterion and its requirement for comparable maximised
likelihoods on the same observations. These fits meet the data and likelihood
convention requirements. Their numerical optimisers are bounded and do not
prove a global optimum. AIC is an asymptotic approximation; early inspections
can leave shape poorly identified, and boundary solutions weaken its usual
justification. The weights are a declared averaging rule, not calibrated
probabilities that a component is the true model.

The ensemble checks each separate fit against the feasible shared-shape
solution for that stratum. If its negative log-likelihood is larger by more
than `1e-8`, bounded PORT optimisation retries from the shared solution and
must converge with a loss no worse than that start. Otherwise the run fails.
This addresses premature convergence on nearly flat likelihoods; it does not
prove a global optimum. The fresh study uses these same refined separate fits
for both the standalone benchmark and the ensemble component. Original
fitters and previous study results are unchanged.

For stratum `g`, the ensemble predicts

\[
S_{g,\mathrm{mix}}(t)=\sum_m w_m S_{g,m}(t).
\]

This mixture need not be Weibull. Averaging shape/scale parameters would give
a different curve. Because expected sale value is linear in survival under
the common inventory, price and cost assumptions, the mixture value curve
equals the weighted sum of component value curves. Choose its earliest
maximising date; do not average the components' chosen dates. Prices are
agreed on the sale day and quality is assessed on delivery. The weights are
constant across strata and forecast dates for a fitted lot.

## API

```r
source("R/model.R")
source("R/sampling.R")
source("R/shared_shape.R")
source("R/shape_ensemble.R")
model <- fit_shape_ensemble(inspections, inventory, decision_day = 12,
                            sensitivity = 0.9, specificity = 0.9)
model$comparison  # parameter counts, likelihoods, AIC, deltas and weights
predict_shape_ensemble(model, c("advanced", "intermediate"), c(20, 20))
decision <- optimal_ensemble_sale(model, prices,
                                  storage_eur_per_kg_day = 0.001,
                                  delivery_lag_days = 2)
```

Training rows after the cutoff are rejected. Initial survival parameters
are placeholders and do not influence fitting. Predictions require aligned
eligible stratum labels and days; there is no implicit vector recycling.
`ensemble_value_grid()` returns the full candidate curve. For one eligible
stratum, both components coincide and receive equal weights. Existing fitters
and their bootstrap APIs retain their original behaviour.

`score_future_probabilities()` in `R/evaluation.R` scores supplied true
acceptance probabilities on independent future counts. It uses the existing
inventory-standardised fruit-level Brier and log loss, allowing the mixture
to be evaluated without forcing it into a single Weibull distribution.

## Prespecified prospective comparison

Use 200 fresh independent base lots and the three generating shape regimes
from [SHARED_SHAPE.md](SHARED_SHAPE.md): common, nearby and strongly different
shapes. Each lot contributes one paired observation per regime; there are
200 independent lots within each regime, not 600 independent lots overall.
The earlier study's outcomes are not reused.

1. Seed `20261104` draws inventory, hypothetical price paths and training
   inspection uniforms. Initial eligible mass is 850 kg. Reported inspections
   occur on days 3/6/9/12, with 180 fruit per stratum/day and known `Se=Sp=0.9`.
2. Fit both components, compute the weights and fix all three sale dates
   before generating any future outcomes. Candidate dates are 12-28, delivery
   lag is two days and holding cost is EUR 0.001 per initial eligible kg/day.
   The ensemble builder receives past counts, public inventory metadata,
   prices and component fits; it does not receive generating survival truth.
3. Seed `20261105` generates future gold-standard inspection counts on days
   16/20/24, with 250 fruit per stratum/day, and fruit lifetimes. Components,
   ensemble and immediate sale share outcomes. Regimes share uniforms but
   retain different distributions and outcomes.
4. Report future Brier/log loss, realised net returns, and the fraction of
   lots returning less than immediate sale. Bootstrap paired whole-lot mean
   differences 1,000 times with seed `9212`; intervals are marginal without
   multiplicity adjustment. Downside fractions use all lots as the denominator
   and count strictly lower returns, so ties do not count as losses.

The weighting rule, scenarios and seeds are fixed before the run. No weights
are tuned to future prediction scores or realised profits. Changing future
seeds cannot change weights, component likelihoods or sale dates. Reordering
or subsetting regimes preserves retained records. Failed fits abort the study
with lot/scenario context; difficult lots are not silently discarded.

## Reproduce and interpret

```sh
Rscript tests/test_shape_ensemble.R
Rscript scripts/run_shape_ensemble.R
# Optional lot count and destination:
Rscript scripts/run_shape_ensemble.R 500 /tmp/orange-shape-ensemble
```

The [saved report](results/shape_ensemble/RESULTS.md) includes paired records,
training likelihoods and weights, a bootstrap summary, settings and a figure.
It reports both gains and losses against each component. Averaging does not
guarantee better future prediction, greater returns or lower downside.

In the saved run, the ensemble has lower mean Brier and log loss than separate
fits in all three regimes, but higher scores than shared shape in all three.
Relative to shared shape, its mean returns decrease by EUR 3.93 and EUR 4.49
for common and nearby shapes. With different shapes, the difference is
EUR +6.71 with a 95% interval of [-1.54, 14.76]; observed losses against
immediate sale occur in 21.5% of lots, compared with 31.0% for shared shape
and 18.5% for separate fits. The ensemble is not a uniformly better policy.

This experiment assumes exact inspection calibration, independent samples,
Weibull deterioration within strata, known prices and negligible sampling
removals. It does not propagate calibration uncertainty or combine storage
shocks and price errors. The mean-difference intervals describe repeated lots;
they are not predictive intervals for an individual lot or uncertainty
intervals for model weights. Empirical model comparison and calibration still
require independent harvest lots under [PROTOCOL.md](PROTOCOL.md).
