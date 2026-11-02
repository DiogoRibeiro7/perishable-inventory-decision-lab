# When deterioration changes after the decision

The earlier studies generate outcomes from the same stratum-specific Weibull
family used for fitting. This experiment tests extrapolation when the true
failure hazard changes after the information cutoff. It evaluates fixed
policies; it does not train a new model on the subsequent outcomes.

## Piecewise hazard generator

For each cohort, let the baseline cumulative hazard be `H(t)=(t/scale)^shape`,
the change point be `tau=12`, and the positive hazard multiplier be `q`.
The stressed survival function is

\[
S_q(t)=\exp\left[-H(\min(t,\tau))
                 -q\{H(t)-H(\min(t,\tau))\}\right].
\]

Up to and including day 12 this is exactly the original curve. There is no
instantaneous probability drop at the cutoff. Afterwards the hazard is `q`
times the baseline hazard. The scenarios are fixed at **q = 1, 0.5, 1.5, 2**:
unchanged, slower, faster and doubled hazard. These are assumptions for a
sensitivity analysis, not estimated temperature effects or storage failures.

Each fruit's baseline failure time `T` is shared across all scenarios. If
`T <= tau`, keep it unchanged. Otherwise transform it to

\[
T_q=\left[\tau^k+(T^k-\tau^k)/q\right]^{1/k},\quad k=\mathrm{shape}.
\]

This preserves the fruit's latent cumulative-hazard quantile. Increasing
`q` can only bring failure forward, while `q=1` returns the exact original
times without consuming random numbers. The analytic survival probabilities
and the transformed empirical lifetime distribution are checked separately.

## Fixed decisions and independent future inspections

1. Prepare 200 independent lots using seed `20261026`. Retain the original
   training inspections at days 3/6/9/12 and fitted stratified/pooled Weibull
   curves. Choose those policies' dates and the existing price-minimax date
   before generating any future outcomes. The price-minimax set stays
   {0.6, 0.8, 1.0}; it receives no deterioration-scenario information.
2. Transform the same fruit lifetimes under each hazard setting. Keep prices
   equal to the original forecast so that this study isolates deterioration
   errors. Sale dates remain fixed; no future rejection rate can revise them.
3. Generate new holdout inspections at days 16/20/24, with 250 fruit per
   cohort/day, using seed `20261027`. Counts are Binomial(n, S_q(day)). Shared
   independent uniforms and binomial inverse CDFs couple the scenarios;
   each scenario retains the correct marginal binomial distribution.
4. Score predicted commercial acceptance with individual-fruit Brier and log
   loss, standardised by eligible inventory mass. Also report predicted minus
   observed acceptable fraction: positive signed bias means overprediction.
5. Compare net returns for stratified, pooled, price-minimax and immediate
   sale using identical fruit within each scenario. Storage is charged on
   initial eligible mass, and commercial acceptance occurs two days after
   sale. **Immediate sale is also exposed between day 12 and delivery day 14.**

The unchanged-hazard row preserves the original generator's economic
outcomes for the same lot seed. Its holdout inspection counts are newly
drawn for coupling across scenarios, so predictive scores need not equal
those from older scripts. Changing the inspection seed changes only quality
measurements; adding/removing/reordering scenarios changes neither lot
generation nor selected dates. Failures abort with a lot identifier rather
than silently discarding difficult lots.

## Inference and interpretation

Use 1,000 whole-lot bootstrap resamples per mean contrast, seed `9189`.
Intervals are marginal and do not adjust for the multiple scenarios or
comparators. Underperformance fractions and 10th percentiles of return
differences are descriptive. Comparisons remain paired within lots.

Proper-score levels depend on outcome prevalence as well as prediction
quality, so cross-scenario score changes alone do not isolate calibration.
Signed bias can also conceal offsetting errors across cohorts or days.
The price-minimax rule minimises fitted expected regret over a finite set of
price paths; it offers no guarantee against this survival-model error. The
old Weibull oracle is omitted because it assumes the unchanged hazard.

## Reproduce

From `studies/orange_storage_decision`, with base R only:

```sh
Rscript tests/test_survival_stress.R
Rscript scripts/run_survival_stress.R
# Optional lot count and destination:
Rscript scripts/run_survival_stress.R 500 /tmp/orange-survival-stress
```

The [saved report](results/survival_stress/RESULTS.md) includes 800 paired
lot/scenario records, summaries, seeds/settings and a calibration/return
figure. The original evaluation, price-sensitivity and minimax studies keep
their original definitions and outputs.

## Limits

The hazard shift is intentionally invisible in pre-cutoff data; it tests an
unobserved regime change, not whether a different model could have predicted
the change from those same inspections. Observed storage covariates and
later forecast updates are outside this experiment. Cohorts share the same
hazard multiplier, lots are independent, sample removals are negligible,
and prices do not respond to deterioration. No empirical quality or profit
claim follows from these synthetic results. See [PROTOCOL.md](PROTOCOL.md)
for the required field measurements and validation.
