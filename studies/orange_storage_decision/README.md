# When Should a Heterogeneous Batch of Oranges Be Sold?

This is an independent **base-R research study** within the
[Perishable Inventory Decision Lab](../../README.md). It complements the main
Python replenishment package; it is not currently integrated with it. The
[migration record](MIGRATION.md) documents its origin and preserved results.

An exploratory, reproducible R case study in postharvest survival analysis and
optimal stopping. The same harvest date does **not** imply the same maturity at
harvest or the same remaining commercial life for every orange.

## Research question

> Can repeated, representative inspections of a small sample of fruit support
> a better sell-or-hold decision for the whole stored batch, without inspecting
> every orange?

The economic problem is to maximise **expected net selling value at delivery**,
not to wait until the last fruit becomes inedible. Fresh-market acceptance is
not identical to food safety, and the model does not certify that fruit is safe
to eat.

## Critical biological boundary

Oranges are non-climacteric: an orange harvested before adequate internal
maturity does not become properly sweet simply through storage. Skin colour
alone is not a reliable maturity label. Initial maturity should be based on
relevant observations such as soluble-solids-to-acidity ratio and quality
inspection, with thresholds appropriate to cultivar, market and regulation.

- UC ANR, [Use taste, rather than rind color, to determine when to harvest
  citrus](https://ucanr.edu/node/111326/printable/print).
- UC Davis Postharvest Center, [Orange: Maturity, Quality and Postharvest
  Handling](https://postharvest.ucdavis.edu/produce-facts-sheets/orange).

An *initially immature* stratum is kept in the inventory example but excluded
from fresh-market revenue. It is not modelled as ripening into the eligible
population. Alternative processing outlets require their own separate quality
thresholds, costs and prices; this version does not optimise those routes.

## Statistical model

At harvest, partition the lot into independently defined maturity/condition
strata, indexed by \(g\), with initial saleable mass \(M_g\). Each initially
eligible stratum has a conditional commercial survival curve

\[
S_g(t)=\Pr(T_g>t\mid g,\text{commercially acceptable at harvest})
     =\exp\left[-\left(t/\lambda_g\right)^{k_g}\right].
\]

Independent, representative cross-sectional inspections observe
\(Y_{g,t}\sim\operatorname{Binomial}(n_{g,t},S_g(t))\). Weibull parameters are
estimated separately by maximising the aggregated binomial likelihood.
Inspections are never treated as individual time-to-event observations.
This is a parametric assumption to validate empirically, not a claim that
real fruit deterioration must be Weibull-distributed.
Multiplying a fruit-count survival fraction by cohort mass additionally assumes
that, within a stratum, the probability of deterioration is not systematically
related to fruit mass. A real application must test this or use mass-weighted
loss measurements.

For a common sale day \(d\), delivery lag \(L\), deterministic expected price
\(p_g(d)\), decision day \(d_0\), and per-initial-kilogram holding cost \(c\),
the illustrative expected value is

\[
V(d)=\sum_{g\in\mathcal E}M_g S_g(d+L)p_g(d)
 - c\left(\sum_{g\in\mathcal E}M_g\right)(d-d_0+L).
\]

Only initially fresh-market-eligible groups \(\mathcal E\) appear. Prices are
locked on the sale day, but the fruit must pass quality inspection at delivery.
Choose the earliest day attaining the highest expected net value. If physical
sorting and separate sales are possible at no extra cost, optimise each stratum
independently as a contrasting upper-bound policy.

### What sampling uncertainty means here

The parametric bootstrap generates inspection counts from the fitted survival
model, refits the curves and recomputes the optimal sale day. It describes
uncertainty due to finite inspection samples *conditional on* the assumed
Weibull specification and supplied price path. Bootstrap failed refits are
counted and reported. Price forecast uncertainty, common storage shocks,
cross-fruit dependence and model misspecification are not included in that
uncertainty interval. The inspection-error extension below conditions on fixed
grading sensitivity and specificity; uncertainty in their calibration is excluded.

## Run the demonstration

Requires R; no external packages, internet, private data or downloaded datasets.

```bash
cd studies/orange_storage_decision
Rscript tests/test_model.R
Rscript scripts/demo.R
```

The seeded demo creates a fictitious 1,000 kg lot with two initially eligible
strata and a 150 kg initially immature stratum. It simulates cross-sectional
inspections at days 4, 8, 12 and 16, fits separate Weibull curves, and makes a
day-16 decision using only observations from days 16 or earlier. A two-day
delivery lag is included. The two cohort-specific price paths and their future
increases are constructed assumptions—not actual orange price forecasts.

The demo prints:

1. Fitted survival shape and scale by eligible stratum.
2. Expected-value-maximising whole-batch sale day.
3. Optimal separately graded sale days and their hypothetical value difference.
4. Bootstrap distribution of the whole-batch sale day and failed refit count.

## Out-of-time policy evaluation

The follow-up experiment compares maturity-stratified Weibull curves with a
mass-standardised, pooled Weibull baseline. It makes decisions using only
day-12 inspections, then scores independent days 16/20/24 and economic
returns on identical simulated fruit outcomes and price paths. Paired
whole-lot intervals measure variation across the simulated harvest lots.

Held-out scoring also supports a single future inspection day and all-pass or
all-fail samples. These do not need to identify a new survival curve. Every
scored day must cover all eligible strata for inventory standardisation;
unequal sample sizes are allowed, but missing strata are rejected explicitly.

```bash
Rscript tests/test_evaluation.R
Rscript scripts/run_policy_evaluation.R
```

Read [EVALUATION.md](EVALUATION.md) for the estimands, leakage controls,
reproducibility settings and interpretation limits. No positive effect is
assumed or claimed in advance.

## Price forecast sensitivity

The [price-error study](PRICE_SENSITIVITY.md) fixes sale dates using the forecast,
then scores the same lots and fruit outcomes under perfect forecasts, unbiased
price noise, and gradually lower mean prices. It reports paired profit
differences and downside against immediate sale, with no future-price leakage.

```bash
Rscript tests/test_price_sensitivity.R
Rscript scripts/run_price_sensitivity.R
```

The [saved synthetic results](results/price_sensitivity/RESULTS.md) include 200
independent lots, shared price errors across grades, paired records and a
reproducible figure. These sensitivity assumptions are not empirical estimates
of orange-market price risk.

## Decisions across uncertain price scenarios

The [minimax-regret policy](ROBUST_POLICY.md) chooses a date that minimises
the largest fitted expected shortfall across a finite set of mean-price
paths. Its [fresh synthetic evaluation](results/robust_policy/RESULTS.md)
compares returns and downside with the forecast-only, pooled and immediate
policies, including mean prices outside the assumed decision set.

```bash
Rscript tests/test_robust_policy.R
Rscript scripts/run_robust_policy.R
```

This rule trades potential upside for protection under its declared scenarios;
it does not guarantee realised profits or beat immediate sale in every lot.

## Survival extrapolation sensitivity

The [deterioration stress study](SURVIVAL_STRESS.md) tests slower and faster
failure hazards after the day-12 decision cutoff. It measures future quality
prediction errors and paired returns while holding fitted policies fixed,
including the price-minimax rule. Immediate sale remains exposed during
delivery. [Saved synthetic results](results/survival_stress/RESULTS.md)
include a reproducible calibration and return figure.

```bash
Rscript tests/test_survival_stress.R
Rscript scripts/run_survival_stress.R
```

## Inspection error correction

The [inspection-error model](INSPECTION_ERROR.md) fits true acceptance when
reported labels contain false accepts or false rejects. It uses externally
calibrated sensitivity/specificity in the binomial likelihood and bootstrap;
perfect inspection remains the default. The [synthetic comparison](results/inspection_error/RESULTS.md)
measures future prediction quality and sale returns against the naive fit.

```bash
Rscript tests/test_inspection_error.R
Rscript scripts/run_inspection_error.R
```

## Finite calibration uncertainty

The [finite-calibration extension](CALIBRATION.md) accepts independent reference
confusion counts and propagates their sampling uncertainty alongside storage
inspection uncertainty. Its [saved example](results/calibration_uncertainty/RESULTS.md)
compares fixed-rate and recalibrated bootstraps, with every failed attempt retained.

```bash
Rscript tests/test_calibration.R
Rscript scripts/run_calibration_uncertainty.R
```

## Shared shape across strata

The [shared-shape model](SHARED_SHAPE.md) estimates one Weibull shape and
separate stratum scales. Its [paired evaluation](results/shared_shape/RESULTS.md)
compares future predictions and sale returns with separate fits under equal,
nearby and strongly different generating shapes.

```bash
Rscript tests/test_shared_shape.R
Rscript scripts/run_shared_shape.R
```

## Averaging survival models

The [shape ensemble](SHAPE_ENSEMBLE.md) weights separate and shared-shape
survival predictions using only the pre-decision inspection likelihoods.
It optimises the averaged value curve. A [fresh paired study](results/shape_ensemble/RESULTS.md)
reports future prediction quality, returns and downside against both component
models and immediate sale across the same three shape regimes.

```bash
Rscript tests/test_shape_ensemble.R
Rscript scripts/run_shape_ensemble.R
```

## Inspection effort and decision value

The [inspection-budget study](INSPECTION_BUDGET.md) compares 30, 90 and 180
checks per stratum/day on the same synthetic lots. Its [saved results](results/inspection_budget/RESULTS.md)
measure prediction quality, sale returns, inspection-cost sensitivity and
the break-even price of each extra check under fixed decision policies.

```bash
Rscript tests/test_inspection_budget.R
Rscript scripts/run_inspection_budget.R
```

## Fruit removed by inspections

The [destructive-inspection extension](INSPECTION_REMOVALS.md) subtracts observed
random removals before valuing sale dates and future holding costs. Its
[paired study](results/inspection_removals/RESULTS.md) distinguishes the change
in fitted inventory value from actual returns when the sale date changes,
using the same remaining fruit for both decisions and immediate sale.

```bash
Rscript tests/test_inspection_removals.R
Rscript scripts/run_inspection_removals.R
```

## Do destructive inspections pay for themselves?

The [inspection-plan comparison](INSPECTION_PLAN_VALUE.md) evaluates three
destructive sampling budgets against fixed no-inspection sales on days 12 and 16.
It follows the same finite fruit population across alternatives, including
holding costs from harvest, labour and forgone sales. The
[saved results](results/inspection_plan_value/RESULTS.md) retain negative gains
and separate timing benefits from removal and labour costs.

```bash
Rscript tests/test_inspection_plan_value.R
Rscript scripts/run_inspection_plan_value.R
```

## Adaptive inspection before a contingent sale

The [one-step sequential policy](ADAPTIVE_POLICY.md) asks whether to commit to
a sale date on day 12 or pay for a nondestructive inspection on day 16 and
revise the selling date from its new quality counts. It uses a prespecified
three-scenario survival prior, exact finite-count value-of-information
enumeration and paired synthetic lots. The comparison includes a no-inspection
commitment, immediate sale and always-inspect benchmark; none receives future
observations before its decision.

```bash
Rscript tests/test_adaptive_policy.R
Rscript scripts/run_adaptive_policy.R
```

This idealised, correctly specified scenario model excludes destructive
removals, noisy labels and price forecast errors; it makes no empirical claim.

## Learning from historical lots

The [historical baseline](HISTORICAL_BASELINE.md) fits stratum survival curves
once on completed historical lots, then chooses sale dates without inspecting
new lots. Its [held-out study](results/historical_baseline/RESULTS.md) compares
returns with fixed-date sales and destructive inspection policies, and measures
future inventory bias and proper prediction scores. Archive-acquisition costs
are excluded explicitly; the model is frozen before target outcomes exist.

```bash
Rscript tests/test_historical_baseline.R
Rscript scripts/run_historical_baseline.R
```

## Uncertainty across historical archives

The [repeated-archive study](ARCHIVE_UNCERTAINTY.md) compares 10 versus 100
historical training lots across 30 independent train/test repetitions. Both
models share fresh target lots within each repetition. Its
[saved results](results/archive_uncertainty/RESULTS.md) report paired return
and prediction differences with intervals that include training-archive
variation, resampling whole repetitions rather than individual target rows.

```bash
Rscript tests/test_archive_uncertainty.R
Rscript scripts/run_archive_uncertainty.R
```

## Historical policies under shelf-life shift

The [historical shift study](HISTORICAL_SHIFT.md) changes target fruit lifetimes
by -25%/0%/+25% while historical fits and sale decisions stay fixed. Its
[paired results](results/historical_shift/RESULTS.md) show how shorter shelf
life can reverse the advantage over immediate sale and produce substantial
inventory overprediction. Intervals include variation across training archives.

```bash
Rscript tests/test_historical_shift.R
Rscript scripts/run_historical_shift.R
```

## Minimax regret over shelf-life scenarios

The [survival-regret rule](SURVIVAL_REGRET.md) selects sale dates across a fixed
set of shorter/unchanged/longer lifetime scenarios. Its
[fresh paired study](results/survival_regret/RESULTS.md) includes shifts beyond
that set and retains the tradeoff: lower worst fitted regret can still worsen
returns under shorter shelf life. The criterion is not a realised-loss guarantee.

```bash
Rscript tests/test_survival_regret.R
Rscript scripts/run_survival_regret.R
```

## Scientific status and limitations

Status: **methodological prototype, synthetic evidence only**. No empirical
profit improvement or predictive accuracy is claimed. This is deliberately
`featured: false` in the portfolio catalogue.

Before application, the study needs representative observations across
multiple harvest lots and storage environments, traceable maturity grading,
predefined market acceptance standards, genuine historical price scenarios,
loss accounting, out-of-lot validation, uncertainty calibration and comparison
against operational baselines. The synthetic prospective simulation does not
replace an empirical out-of-lot test. See [PROTOCOL.md](PROTOCOL.md) for the
proposed empirical design and anti-leakage rules.
