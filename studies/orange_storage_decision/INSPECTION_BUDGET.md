# The decision value of additional inspections

More observations can improve survival estimates without improving the sale
decision enough to cover their cost. This study compares three inspection
plans under fixed modeling rules, measures paired return differences, and
calculates the cost at which extra inspections stop paying for themselves
on average in the synthetic population.

## Plans, policies and assumptions

The inspection schedule remains days 3/6/9/12, with a day-12 decision and
candidate sale days 12-28. Only the number checked per stratum/day changes:

| Plan | Per stratum/day | Two strata, four days | Extra checks over smallest plan |
|---|---:|---:|---:|
| Small | 30 | 240 | 0 |
| Medium | 90 | 720 | 480 |
| Large | 180 | 1,440 | 1,200 |

All plans use the [AIC-weighted ensemble](SHAPE_ENSEMBLE.md), and are also
evaluated with its separate and shared-shape components. The separate
component includes the existing feasible-start refinement. AIC compares
components within a plan, on the same inspection data; AIC scores from
different sample budgets are not compared to choose a budget.

The three generating regimes are common, nearby and strongly different
Weibull shapes, as defined in [SHARED_SHAPE.md](SHARED_SHAPE.md). Initially
eligible mass is 850 kg, delivery takes two days, holding cost is EUR 0.001
per initial eligible kg/day, and inspection sensitivity/specificity are
known and equal to 0.9. The same hypothetical price paths apply to all plans.

This experiment assumes nondestructive inspections that do not change
inventory or deterioration. It retains independent cross-sectional binomial
sampling. A larger destructive sample would remove sellable fruit and
requires a different inventory and cost model; the linear inspection charge
here does not account for that loss. Handling effects, repeated-fruit
dependence, fixed visit costs and external calibration costs are excluded.

## Economic estimands

Let `V_bi` be the realised sale return, after storage and delivery rejection
but before inspection charges, for plan `b` on lot `i`. With `N_b` total
checks and a common unit charge `c`, its planning payoff is

\[
U_{bi}(c)=V_{bi}-N_b c.
\]

For a larger plan `b` versus the smallest plan `a`, estimate

\[
\Delta U_{b,a}(c)=\overline{V_b-V_a}-(N_b-N_a)c,\qquad
c^*_{b,a}=\frac{\overline{V_b-V_a}}{N_b-N_a}.
\]

The break-even threshold `c*` concerns the **mean incremental** return of
the specified policy. Below a positive threshold, the larger plan has a
higher estimated mean payoff; above it, the smaller plan does. Negative
thresholds are retained: a larger plan can have a lower mean return even
when extra checks are free. Dividing the paired return interval by the
positive, fixed number of extra checks gives the threshold interval.

Cost summaries use hypothetical charges of EUR 0, 0.02, 0.05 and 0.10 per
inspected fruit. These are sensitivity values, not observed market prices.
They subtract **all** checks when comparing with a prespecified day-12
immediate sale that requires no inspections. Underperformance fractions
count strictly lower net returns, with all lots in the denominator.

Inspection expenditure occurs before the decision cutoff. It matters when
choosing a plan in advance; after collection it is sunk and equal across
candidate sale dates within that plan. Cost sensitivity therefore does not
refit models or change their selected dates. Common pre-cutoff storage and
initial harvest-grading costs remain excluded from all policy returns.

This is a simulation comparison of fixed policies and inspection schedules.
It does not optimise over all possible information-gathering strategies,
claim a formal Bayesian expected value of sample information, or recommend
an empirically optimal budget.

## Prospective paired simulation

1. Declare the plans, models, shape regimes and cost grid before the run.
2. Use 200 fresh independent base lots. For each plan, reset training seed
   `20261106`, preserving inventory, prices and the eight inspection uniforms.
   Transform these uniforms using binomial inverse CDFs at the plan's sample
   size. Each plan has the correct marginal count distribution.
3. For each plan, fix every model and sale date using only its day-3/6/9/12
   counts, before drawing that plan's future outcomes. Reset outcome seed
   `20261107` to give all plans the same fruit lifetimes and gold-standard
   future inspections at days 16/20/24 (250 per stratum/day).
4. Score inventory-standardised fruit-level Brier/log loss, sale returns and
   cost-adjusted payoffs. Compare each higher budget with 30 per stratum/day,
   within each model and shape regime. Bootstrap paired whole-lot differences
   1,000 times with seed `9213`. Intervals are marginal without multiplicity
   adjustment, and concern population means under this simulator.

The inverse-CDF coupling reduces Monte Carlo variation in differences; it
does not model enlarging an actual pilot sample with additional independent
observations. The three plans and three regimes are paired representations
of 200 base lots, not 1,800 independent lots. No budget or policy uses future
results from another plan. Changing the future seed leaves fits and dates
unchanged. Reordering/subsetting plans preserves retained records. Any fit
failure aborts with budget, lot and scenario context rather than dropping
that lot from the comparison.

## API and reproduction

```r
# Source the same modules as scripts/run_inspection_budget.R.
records <- run_inspection_budget_experiment()
summary <- summarize_inspection_budgets(records, costs = c(0, 0.02, 0.05, 0.10))
set.seed(9213)
contrasts <- compare_inspection_budgets(records, n_boot = 1000)
```

```sh
Rscript tests/test_inspection_budget.R
Rscript scripts/run_inspection_budget.R
# Optional lot count and destination:
Rscript scripts/run_inspection_budget.R 500 /tmp/orange-inspection-budget
```

The [saved report](results/inspection_budget/RESULTS.md) includes all paired
records, cost summaries for all three models, contrasts, settings and a
figure. Earlier model studies retain the default 180 checks per stratum/day
and their existing results.

In the saved run, all six larger-versus-smallest ensemble comparisons have
lower mean Brier scores. At the hypothetical EUR 0.02 per check, only the
90-check plan under common and nearby shapes retains a positive mean gain
over the 30-check plan (EUR 6.90 and EUR 6.27 per lot). Its break-even prices
are EUR 0.0344 and EUR 0.0331 per extra check; the 180-check plan's corresponding
thresholds are lower, EUR 0.0183 and EUR 0.0180. These are comparisons with
the smallest inspection plan: all three ensemble plans still have negative
mean net advantages against immediate sale in those two regimes at EUR 0.02.

Under different true shapes, the ensemble's additional-data return intervals
include zero. The shared-shape policy loses EUR 8.02 on average when moving
from 30 to 180 checks, even before inspection charges (95% interval
[-14.24, -2.73]). More observations alone do not guarantee a better sale policy.

Empirical sampling-design decisions require
representative lots, measured inspection costs and operational validation
under [PROTOCOL.md](PROTOCOL.md).
