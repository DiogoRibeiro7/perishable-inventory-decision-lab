# Value of destructive inspection plans

The [removal-ledger study](INSPECTION_REMOVALS.md) compared decisions after
inspections had already happened. Its immediate-sale comparator had already
lost the same sampled fruit. That comparison cannot establish whether the
inspection plan itself is worthwhile.

This experiment compares three prespecified destructive sampling plans with
**no inspection and sale on day 12 or day 16**. The no-inspection policies retain
all eligible fruit and pay no inspection labour. Both dates are fixed before
evaluation. Sale before day 12 is outside the decision set: these are operational
benchmarks, not optimal no-inspection policies or a day-zero sale comparison.

## Population, sampling and fitting

Each of 200 independent synthetic lots uses the original nearby-shape generator:
advanced/intermediate Weibull shapes centred on 2.2/1.8 and scales on 18/36,
with the existing lognormal variation. Eligible inventory is 850 kg (4,250 fruit
of 0.20 kg). The advanced mass allocation is rounded to a multiple of 0.20 kg;
the intermediate stratum contains the remainder. The 150 kg initially immature
stratum is excluded from fresh-market sales and eligible holding costs.

Plans are fixed at 30, 90 or 180 checks per eligible stratum on days 3/6/9/12.
They remove 240/720/1,440 fruit, or 48/144/288 kg, regardless of reported quality.
All original strata contain enough fruit for the largest plan. There is no
selective culling, repeated inspection of an individual fruit, or replacement
of destroyed fruit.

The simulator generates one finite population of latent lifetimes per lot.
It assigns a random permutation of fruit IDs to four disjoint daily blocks of
180 slots within each stratum. Smaller plans take nested prefixes of those
blocks. Thus plans share the same sample labels when they inspect the same fruit
and the same remaining-fruit outcomes wherever their inventories overlap.
Removing fruit never changes another fruit's lifetime in this model.

Labels use fixed, known sensitivity and specificity of 0.90. Given the latent
stratum parameters, fruit lifetimes and grading errors are independent. Disjoint
cross-sectional samples therefore support the existing binomial likelihood;
the model is not fitted to longitudinal outcomes or a finite-population total
treated as known.

At day 12, each plan fits the same separate/shared-shape AIC mixture to its own
observed counts, then selects the earliest maximum of the remaining-inventory
value curve. The policy receives only aggregate counts through day 12, initial
inventory metadata, observed removal masses and the supplied price path. Its
inventory shape/scale fields are placeholders before fitting. Fruit IDs, raw
lifetimes and true parameters do not cross that interface.

Unlike experiments that generate an independent evaluation population, latent
lifetimes here must exist before labels can be sampled. This is confined to the
simulator. Future survival affects evaluation only; changing post-cutoff failure
times while preserving all earlier pass/fail states leaves inspection records
unchanged. All three decisions are fixed before scoring the lot. The sale grid
is days 12--28, delivery lag two days, and prices are hypothetical and perfectly
known. No plan is selected or retuned using these evaluation outcomes.

## Holding costs and physical accounting

All comparisons charge EUR 0.001 per eligible physical kg/day **from harvest
through delivery**, whether fruit is still acceptable or has failed. For initial
mass \(M_g\) and removals \(r_{gj}\) on days \(t_{gj}\le d_0\), pre-decision
holding cost is

\[
 C_{\mathrm{past}} = c\left[d_0\sum_g M_g
   -\sum_{g,j}r_{gj}(d_0-t_{gj})\right].
\]

Future holding cost is \(c(d+\ell-d_0)\sum_g(M_g-\sum_jr_{gj})\).
For an uninspected lot the combined cost is \(c(d+\ell)\sum_g M_g\).
Ignoring pre-decision storage savings would unfairly charge the inspection plans
for fruit no longer in storage.

`predecision_holding_cost()` in [inspection_plan_value.R](R/inspection_plan_value.R)
uses the existing ledger validation, including rejection of future observations
and over-removals. Example from this project directory:

```r
source("R/model.R")
source("R/inspection_removals.R")
source("R/inspection_plan_value.R")
inventory <- data.frame(cohort = "eligible", mass_kg = 100,
  initially_sellable = TRUE, shape = 2, scale = 20)
removals <- data.frame(cohort = "eligible", day = 3, mass_kg = 20)
predecision_holding_cost(inventory, removals, 0.001, 12) # EUR 1.02
```

Evaluation excludes exactly the inspected fruit IDs from sales. It deducts
holding and hypothetical inspection labour, with no additional market-value
charge for destroyed fruit: their forgone revenue is already absent. Labour is
varied over EUR 0/0.02/0.05/0.10 per check. Within a fixed plan this is a sunk
constant at day 12, so it does not change the selected date.

## Estimands and uncertainty

Report paired mean net returns against both no-inspection benchmarks, marginal
95% whole-lot percentile bootstrap intervals and the fraction of strictly lower
returns. Every denominator is the 200 independent lots. The three correlated
plan rows for a lot are never counted as three independent replications.

For the day-12 comparison, each lot satisfies this accounting identity:

\[
 \Delta V = \text{timing gain on remaining fruit}
             - \text{net removal cost} - \text{inspection labour}.
\]

Timing gain compares the fitted sale date with day-12 sale after the same
removals. Net removal cost is the inspected fruit's forgone day-12 sale revenue
less its saved holding cost from removal through day-14 delivery. Removing a
fruit that would be rejected at delivery can save holding cost without losing
sale revenue; negative net removal costs are retained.

Break-even labour charge is the mean return difference **before labour** divided
by the fixed number of checks. It uses the same interval divided by that count.
A negative result means there is no nonnegative labour price at which this
policy breaks even on average against day-12 no-inspection sale. It is not the
optimal value of information and does not rule out other inspection strategies.
Cost sensitivity shifts the paired intervals by a deterministic labour bill;
it does not rerun or retune policies. Intervals are not multiplicity-adjusted.

## Saved findings

The [full report](results/inspection_plan_value/RESULTS.md) contains 600 paired
plan records. At EUR 0.02 per check:

| Checks/stratum/day | Mean gain vs no-inspection day 12 (EUR) | 95% interval |
|---|---:|---:|
| 30 | -41.09 | [-49.17, -32.25] |
| 90 | -95.07 | [-101.63, -88.59] |
| 180 | -184.30 | [-189.63, -179.29] |

All three plans also lose on average against day-16 no-inspection sale. Even
with free labour, the mean differences against day 12 remain negative, with
intervals below zero. The largest plan gains EUR 4.00 by adjusting its sale date
after inspection, but net removal cost is EUR 159.50 and labour is EUR 28.80.
The smallest plan's mean timing gain is itself negative (EUR -9.57), illustrating
that a fitted optimum need not improve realised outcomes.

These findings concern fixed synthetic plans and one regime. They do not
establish field economics, the best sampling design, or that all inspections are
unhelpful. Historical-data policies, smaller samples, other inspection days,
nondestructive tests, earlier sales and empirical costs may change the result.
Dependence, handling damage, disposal/processing value, imperfect price forecasts,
uncertain grading calibration and mass-dependent failure are excluded.

## Reproduction

```sh
Rscript tests/test_inspection_plan_value.R
Rscript scripts/run_inspection_plan_value.R 200
```

The optional second argument is the output directory. Metadata, finite fruit
populations and sample assignments use separate seeds `20261110`, `20261111`
and `20261112`. Bootstrap seed is `9215`, with 1,000 resamples. Seeds, costs,
budgets and benchmarks were fixed before the full run. Saved settings also
record R version and RNG kind. Tests rebuild the summary from committed records
and check analytical storage costs, individual-fruit exclusion, nested samples,
the information boundary and the lot-level accounting identity.
