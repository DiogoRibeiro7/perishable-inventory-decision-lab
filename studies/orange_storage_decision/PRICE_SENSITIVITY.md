# When future prices differ from the forecast

The original prospective experiment gives every policy the prices that will
actually occur. This extension measures sensitivity to price forecast errors
while keeping the survival fits and chosen selling dates fixed. It remains a
synthetic stress test; its price parameters are not estimated from market data.

## Decision and outcome separation

For each independent lot, fit stratified and pooled survival curves from days
3/6/9/12 and choose sale dates from the original forecast. Prepare held-out
quality inspections and a common set of fruit failure times. Only after all
lots and decisions have been prepared, start a separately seeded price process.
Changing that seed, adding a scenario or reordering scenarios cannot change
the lots, fitted decisions, quality scores or fruit outcomes.

Every policy and price scenario on a lot shares those fruit outcomes. Price
errors are shared across grades and persist over time. Policies receive no
realised future prices, and are not re-optimised after seeing an error. This
evaluates the existing day-12 commitments, not an adaptive trading strategy.
Prices are locked at sale; commercial acceptance remains assessed two days
later. Immediate sale uses the known day-12 quote in every scenario.

## Price process and predeclared scenarios

Let `f_g(d)` be the forecast price for grade `g`, `u=(d-12)/16` the fraction of
the sale horizon elapsed, and `B(u)` standard Brownian motion shared by grades.
The actual sale price is

\[
p_g(d)=f_g(d)m^u\exp\{\sigma B(u)-\tfrac12\sigma^2u\}.
\]

The conditional mean actual/forecast ratio is `m^u`; terminal log-error
standard deviation is `sigma`. The variance correction prevents unbiased
log-price noise from systematically increasing expected prices. Independent
standard-normal innovations are multiplied by the square root of the elapsed
time increments, so the transform also handles irregular quote grids.

| Scenario | Terminal mean ratio `m` | Terminal log-error SD `sigma` |
|---|---:|---:|
| Perfect forecast | 1.0 | 0 |
| Unbiased noise | 1.0 | 0.2 |
| Mean 20% below forecast | 0.8 | 0.2 |
| Mean 40% below forecast | 0.6 | 0.2 |

The last two settings gradually lower mean prices to 80% or 60% of the
forecast at day 28. They use the same innovations as the unbiased scenario.
The decision-day price is unchanged. No scenario is selected from its results.

## Measurements

- Mean realised net revenue for stratified, pooled and immediate-sale policies.
- Stratified minus pooled and stratified minus immediate revenue, paired
  within each lot; 95% percentile intervals bootstrap entire lot differences.
- Fraction of lots in which each fitted policy earns less than immediate
  sale, with exact ties excluded; the 10th percentile of stratified minus
  immediate revenue describes downside rather than uncertainty in the mean.
- Price-error impact relative to the same policy's realised perfect-forecast
  revenue, with all fruit outcomes held fixed.

Scenarios are dependent comparisons on the same lots. Reported mean intervals
are marginal, without adjustment for inspecting multiple scenarios; downside
fractions and percentiles are descriptive. Unbiased price noise preserves
conditional mean revenue for fixed policies but can increase downside risk.
Finite-sample means can still differ. Biased prices can change both mean and
downside outcomes.

The original oracle uses true survival curves and the original forecast. Under
a biased price process it need not maximise true expected value, so this study
does not report its outcomes or label any difference as oracle regret.

## Reproduce

From `studies/orange_storage_decision`, with base R only:

```sh
Rscript tests/test_price_sensitivity.R
Rscript scripts/run_price_sensitivity.R
# Optional lot count and output directory:
Rscript scripts/run_price_sensitivity.R 500 /tmp/orange-price-sensitivity
```

The default run uses 200 independent lots, simulation seed `20261022`, price
seed `20261023`, bootstrap seed `9187` and 1,000 resamples per mean contrast.
It writes paired records, summaries, settings, a report and a figure under
[`results/price_sensitivity`](results/price_sensitivity/RESULTS.md). The
perfect-forecast measurements retain the original experiment's seeded lots;
the original `run_policy_evaluation.R` output is unchanged.

Tests integrate the price transform against a normal density to verify its
conditional mean, check irregular quote spacing and shared grade errors,
and verify that future prices cannot change fixed decisions. They also check
paired summaries and invariance to scenario order, subsets and price seed.

## Limits

The follow-up [minimax-regret study](ROBUST_POLICY.md) uses these findings to
motivate a finite mean-price decision set, then evaluates a new policy on
fresh simulated lots. This original study remains a fixed-policy comparison.

There are no historical orange prices or empirical forecast residuals here.
The model assumes one perfectly shared grade-price shock, independent lots,
no price–spoilage dependence, fixed storage costs, negligible inspection
withdrawals, and correctly specified Weibull deterioration. It does not model
market constraints, forecast updates, selling in several transactions, or
responses to newly observed prices. Synthetic findings do not establish field
profitability or commercial-quality safety. Empirical forecasting and
lot-blocked evaluation remain requirements in [PROTOCOL.md](PROTOCOL.md).
