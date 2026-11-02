# Choosing a sale date under uncertain mean prices

The [price sensitivity study](PRICE_SENSITIVITY.md) found that a policy based
on an optimistic forecast can lose its advantage over immediate sale. This
extension adds a **finite-scenario minimax-regret policy** and evaluates its
tradeoffs on fresh synthetic lots. It is a methodological experiment, not a
commercial recommendation or an empirically calibrated risk model.

## Decision criterion

At day 12, fit the same stratum-specific Weibull curves from inspections on
days 3/6/9/12. For each candidate sale day `d` and declared mean-price scenario
`s`, calculate expected net return `V_s(d)` using those fitted curves, holding
costs and the two-day delivery lag. Define

\[
R_s(d)=\max_t V_s(t)-V_s(d),\qquad
d^*=\arg\min_d\max_s R_s(d).
\]

Ties select the earliest date. Each scenario's best date is a comparator
within the fitted model; it has no knowledge of realised fruit outcomes.
This criterion minimises the largest expected opportunity loss across the
listed scenarios. It differs from maximising worst-case profit or expected
profit under an assigned probability distribution. No scenario probabilities
are assumed. It is not CVaR or a guarantee against losing to immediate sale.

The decision set has three terminal mean actual/forecast ratios:
**{0.6, 0.8, 1.0}**. On day `d`, multiply the original forecast by
`m^((d-12)/16)` for each ratio `m`. All scenarios agree on the known current
quote, grade coverage and candidate sale dates. The set is finite; there is
no claim of optimisation over every intervening mean or arbitrary price path.

`minimax_regret_sale()` also accepts a named list of custom complete mean
price grids. It returns the chosen date, every candidate's worst expected
regret, and the scenario/date value table for inspection. With a single
scenario, it reduces to the ordinary expected-value policy.

## Prospective evaluation

The earlier price study motivated the decision set. This is an exploratory
follow-up with fresh random seeds, not a preregistered empirical validation.
The rule and set are fixed before evaluating these new lots; no grid search
or selection based on their outcomes is performed.

1. Generate 200 independent lots using seed `20261024`. Fit both existing
   policies and choose the additional minimax date using only fitted
   inventory and forecasts. The policy callback runs before held-out
   inspections or fruit failure times are generated.
2. After preparing all lots, draw price innovations using seed `20261025`.
   Every policy and evaluation scenario shares the lot's fruit outcomes and
   innovations. Changing evaluation scenarios or the price seed cannot
   change selected dates or survival fits.
3. Evaluate perfect forecasts, unbiased noise, and terminal mean ratios
   0.8, 0.6, **0.4 and 1.2**. The latter two means are outside the decision
   set. Every noisy setting uses terminal log-error SD 0.2 and the original
   mean-corrected Brownian price process. A mean-price scenario is not a
   bound on its stochastic realised paths.
4. Compare minimax, forecast-only stratified, pooled and immediate-sale
   returns on the same lots. Report paired mean differences, 1,000 whole-lot
   bootstrap resamples per contrast (seed `9188`), strict underperformance
   fractions and 10th percentiles of differences against immediate sale.

Intervals are marginal and do not adjust for multiple scenarios/comparators.
Downside fractions and percentiles are descriptive; the policy does not
directly optimise them. A better average result in an adverse scenario can
come with a lower average return when forecasts are accurate or pessimistic.
The report retains both outcomes without averaging over arbitrary scenario
weights. Mean sale dates help show how the policy changes its commitments.

## Reproduce and inspect

From `studies/orange_storage_decision`, using base R:

```sh
Rscript tests/test_robust_policy.R
Rscript scripts/run_robust_policy.R
# Optional lot count and destination:
Rscript scripts/run_robust_policy.R 500 /tmp/orange-robust-policy
```

The [saved report](results/robust_policy/RESULTS.md) links 1,200 paired records,
all summary metrics, seeds/settings and a figure. The existing evaluation
and price-study outputs remain reproducible with their original seeds.

## Limits

The separate [survival stress study](SURVIVAL_STRESS.md) evaluates this fixed
price-minimax rule when deterioration changes after day 12, while actual
prices equal the original forecast. It tests an assumption the rule does not
protect against.

Robustness is conditional on the supplied survival fits, costs, available
dates and finite mean-price set. Poor survival fits, miscalibrated scenario
means, grade-specific shocks or dependence between price and spoilage can
invalidate its apparent protection. There are no historical market data,
adaptive forecast updates, split transactions or buyer constraints here.
Fresh simulated lots quantify behaviour under the chosen generator; they do
not establish field profitability. The empirical requirements in
[PROTOCOL.md](PROTOCOL.md) still apply.
