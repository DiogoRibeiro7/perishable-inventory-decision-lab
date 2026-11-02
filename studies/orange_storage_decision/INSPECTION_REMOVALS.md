# Destructive inspection accounting

The [inspection-budget study](INSPECTION_BUDGET.md) treats checks as
nondestructive. A destructive check removes fruit from the physical inventory,
including fruit that passed inspection. The extension in
[inspection_removals.R](R/inspection_removals.R) accepts an observed removal
ledger and values only the fruit still present at the decision cutoff.

## Ledger and model contract

Keep the original harvest inventory and fitted survival curves. Supply a data
frame with one aggregated row per stratum and removal day:

| Field | Meaning | Constraint |
|---|---|---|
| `cohort` | Initial inventory stratum | Known character identifier |
| `day` | Days since harvest | Whole day from zero through `decision_day` |
| `mass_kg` | Total physical mass removed that day | Positive and finite |

An empty ledger is valid. Duplicate stratum/day rows, unknown strata, future
removals and total removals exceeding initial mass are rejected. Floating-point
roundoff at exact depletion is tolerated. Prices must cover the original
eligible strata and all candidate sale dates, including depleted strata.

For initial mass \(M_g\), observed removal mass \(R_g\), and fitted survival
\(S_g\), expected acceptable mass at delivery is

\[
  \sum_{g\text{ initially eligible}} (M_g-R_g)S_g(d+\ell).
\]

Each stratum's acceptable mass receives its sale-day price. Future holding cost
is charged on the remaining eligible physical mass for \(d-d_0+\ell\) days.
Past holding and inspection costs are sunk and excluded from this optimisation;
they can be subtracted when reporting total returns.

This calculation requires random, nonselective removal within each initial
stratum, independent of fruit lifetime and mass. Removing only fruit judged
unacceptable changes the composition of the remainder and requires a different
model. Remaining fruit have not all passed a cutoff-day inspection, so survival
is **not** divided by \(S_g(d_0)\). The original mass-to-acceptance calculation
also assumes fruit mass and failure time are unrelated within a stratum.

Fully depleted strata contribute no sales or future holding cost. If all eligible
fruit have been removed, every candidate has zero future value and the earliest
date wins the tie. This does not reimburse costs already incurred.

## Use

From `studies/orange_storage_decision`:

```r
source("R/model.R")
source("R/inspection_removals.R")

inventory <- data.frame(
  cohort = c("advanced", "intermediate"), mass_kg = c(350, 500),
  initially_sellable = TRUE, shape = c(2.2, 1.8), scale = c(18, 36)
)
prices <- expand.grid(cohort = inventory$cohort, day = 12:28,
                      stringsAsFactors = FALSE)
prices$price_eur_per_kg <- 1
removals <- expand.grid(cohort = inventory$cohort, day = c(3, 6, 9, 12),
                        stringsAsFactors = FALSE)
removals$mass_kg <- 36
optimal_sale_after_removals(inventory, prices, removals,
  storage_eur_per_kg_day = 0.001, decision_day = 12, delivery_lag_days = 2)
```

Here the survival parameters and prices are illustrative. For a fitted
`fit_shape_ensemble()` model, use `ensemble_value_after_removals()` or
`optimal_ensemble_sale_after_removals()`. Each component uses the same observed
ledger; fitted curves and training-only AIC weights remain fixed. An empty
ledger reproduces the existing value functions.

## Fixed-plan paired experiment

[removal_evaluation.R](R/removal_evaluation.R) compares two day-12 decisions:
one uses original masses, the other uses remaining masses. Both use exactly
the same AIC-weighted separate/shared-shape survival fit and price path.

- Generate 200 independent lots using the original nearby-shape generator:
  advanced/intermediate shapes centred on 2.2/1.8, scales on 18/36, and the
  existing lognormal variation. Eligible mass is 850 kg, with the advanced
  allocation rounded to a multiple of 0.20 kg. The 150 kg immature stratum
  remains excluded from sales and holding cost.
- Draw 180 fresh fruit per eligible stratum on days 3/6/9/12. Every inspected
  fruit is removed, regardless of its reported label. At 0.20 kg per fruit,
  1,440 checks remove 288 kg, leaving 562 kg or 2,810 fruit. Each stratum has
  sufficient inventory for this fixed plan.
- Reported acceptable counts follow the binomial measurement model with known
  sensitivity and specificity of 0.90. Conditional on lot parameters, fruit
  lifetimes are independent; disjoint random inspection samples and the
  uninspected remainder are therefore independent. Removed fruit cannot appear
  in the evaluated remaining population or be sampled twice.
- Fix both policies using only initial inventory metadata, observed counts,
  past removals and the supplied price path. Candidate sale days are 12--28,
  delivery lag is two days and holding cost is EUR 0.001 per remaining eligible
  kg/day. All lots' decisions precede generation of remaining-fruit outcomes.
- Evaluate both policies and immediate day-12 sale on identical remaining
  fruit lifetimes. Subtract EUR 28.80 inspection labour from every policy,
  including immediate sale: all have already completed the same plan.
  This common sunk cost cancels in paired decision contrasts.

Training seed: `20261108`; remaining-outcome seed: `20261109`; bootstrap seed:
`9214`. Mean contrasts use 1,000 paired whole-lot percentile bootstrap resamples
and marginal 95% intervals, with no multiplicity adjustment. True expected
returns use the generating curves only for evaluation. They are unavailable
to policy fitting. Downside frequencies count strictly lower realised returns
across all lots, including lots with unchanged dates.

## Saved findings and limits

The [saved results](results/inspection_removals/RESULTS.md) separate three
quantities that should not be confused:

| Contrast | Mean EUR/lot | 95% paired-lot interval |
|---|---:|---:|
| Original minus corrected fitted value at the old date | 163.76 | [158.97, 169.32] |
| True expected gain from changing the date | 0.03 | [-1.20, 1.07] |
| Realised gain from changing the date | 0.08 | [-1.14, 1.23] |

Accounting changes 16.5% of dates. The revised date earns less than the original
date on 4.0% of lots. Its mean advantage over immediate sale after the same
inspections is EUR 6.29 [1.67, 11.07], with 7.5% of lots below immediate sale.
The inventory correction is material, while these simulations provide no clear
evidence of a mean return improvement from the changed dates.

This is a conditional comparison after one completed inspection plan. There is
no no-inspection comparator, and it does not establish the value of inspections
or compare destructive and nondestructive sampling. A separate
[plan-value study](INSPECTION_PLAN_VALUE.md) now compares fixed destructive
budgets with no-inspection sale benchmarks. Equal proportional removals
would simply scale the value curve; equal numbers removed from unequal strata
can change its shape and optimal date. Handling damage, selective culling,
disposal costs/revenue, dependence, calibration uncertainty and price errors are
excluded. Synthetic results do not establish field profitability.

```sh
Rscript tests/test_inspection_removals.R
Rscript scripts/run_inspection_removals.R 200
```

The generator also accepts an output directory as its second argument. Saved
records, summary, settings and figure allow the findings to be audited; tests
rebuild the committed summary from its records and bootstrap seed.
