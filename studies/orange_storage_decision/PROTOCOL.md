# Prospective protocol: inspection-driven orange sales

## Target decision

At each decision day, recommend one common sale day for the remaining
fresh-market-eligible inventory, or separate sale days when grades can be
physically segregated. The quality requirement applies at **delivery** and
is determined by market acceptance criteria independently of the model.

## Unit of analysis and sampling frame

- Harvest lot: cultivar, orchard block, harvest date, packing history and
  storage environment recorded before outcomes are observed.
- Predefined stratum: a maturity/condition category established at harvest.
  Colour is not an adequate substitute for internal quality assessment.
- Fruit inspection: sample identifiers, stratum, inspection day, random
  selection method, soluble solids, titratable acidity, firmness, defects,
  commercial pass/fail outcome and reason for failure.
- Cross-sectional design: draw fresh, representative random samples within
  each stratum at each inspection day. If fruit is inspected repeatedly,
  use a longitudinal survival model instead of the independent-binomial
  likelihood currently implemented.
- Destructive sampling: record and subtract removed fruit from sellable
  inventory. The [removal-ledger extension](INSPECTION_REMOVALS.md) implements
  this for random samples within each initial stratum, regardless of quality.
  Selective culling needs a different model; the original value functions
  still assume negligible removals unless the extension is used.
- Mass accounting: record fruit mass in inspection samples, because multiplying
  acceptable-fruit proportions by inventory kilograms assumes no relationship
  between fruit size and loss probability within a cohort.
- Storage: daily temperature/humidity traces, handling, handling damage and
  any removal/disposal events. Record both sale date and actual delivery date.

## Data contract

An aggregated inspection table uses:

| Field | Unit | Constraint |
|---|---|---|
| `cohort` | category | Preassigned at harvest; never future-defined |
| `day` | days since harvest | Positive whole day, unique per cohort/day |
| `n_checked` | fruit | Positive integer |
| `n_acceptable` | fruit | Integer from zero to `n_checked` |

The initial inventory records `cohort`, `mass_kg`, and
`initially_sellable`. The price scenario records a day-by-cohort gross price
in EUR/kg. Weibull `shape` and `scale` are positive and fitted from historical
inspections; placeholder values in the demonstrator are not real estimates.

## Fitting and evaluation without leakage

1. Define grading criteria and strata using information available at harvest.
2. Choose an inspection plan before observing subsequent deterioration.
3. At decision day \(d_0\), fit the survival model using inspections with
   `day <= d_0` only; never use subsequent losses to classify cohorts.
4. Calibrate/compare models with harvest-lot-level held-out validation. Random
   rows from the same lot do not constitute an independent test set.
5. Compare observed acceptable fractions with predicted survival using
   calibration plots, proper scores and uncertainty coverage across lots.
6. Assess the decision against prespecified baselines: sell immediately,
   fixed storage-duration policy, and pooled (unstratified) survival policy.
7. Evaluate realised net return including unsold inventory, storage,
   handling, delivery rejection, disposal and processing revenue, as
   applicable. Do not treat synthetic optimal expected value as realised
   economic improvement.

## Baseline model and sensitivity plan

- Primary prototype: stratum-specific Weibull survival with independent
  binomial inspections; fixed deterministic price path.
- First synthetic comparator implemented: mass-standardised pooled Weibull,
  paired economic decisions, held-out inspections at future days and
  harvest-lot bootstrap intervals. See [EVALUATION.md](EVALUATION.md).
- Survival extrapolation sensitivity implemented: a post-cutoff piecewise
  hazard shift, coupled fruit outcomes, future quality scores and fixed-policy
  returns. See [SURVIVAL_STRESS.md](SURVIVAL_STRESS.md). Empirically observed
  storage-covariate shifts remain open.
- Alternative fitted model implemented: one common Weibull shape with separate
  stratum scales. Paired prospective evaluation includes equal, nearby and
  strongly different true shapes. See [SHARED_SHAPE.md](SHARED_SHAPE.md).
  Empirical model selection and uncertainty coverage remain open.
- Model averaging implemented: training-only AIC weights combine separate and
  shared-shape survival predictions before optimising sale value. Fresh paired
  lots compare the mixture with both components and immediate sale, retaining
  negative effects. See [SHAPE_ENSEMBLE.md](SHAPE_ENSEMBLE.md). Empirical weights,
  calibration and joint model/calibration uncertainty remain open.
- Inspection-error correction implemented: a binomial measurement model with
  externally fixed sensitivity/specificity, compatible parameter bootstrap,
  and paired synthetic comparison against naive fitting. See
  [INSPECTION_ERROR.md](INSPECTION_ERROR.md).
- Finite calibration uncertainty implemented: independent reference confusion
  counts and paired conditional/recalibrated parametric bootstraps, retaining
  invalid calibration draws and failed refits. See [CALIBRATION.md](CALIBRATION.md).
  Coverage across independent lots, calibration drift, reference-label errors,
  inspection-frequency changes and within-lot dependence remain open.
- Price-path sensitivity implemented: forecast-based dates evaluated on shared
  realised price errors, with biased/unbiased scenarios and paired downside
  summaries. See [PRICE_SENSITIVITY.md](PRICE_SENSITIVITY.md). The price-error
  process is assumed; it still needs empirical calibration.
- Finite-scenario decision rule implemented: minimise worst fitted expected
  regret across declared mean-price paths. Fresh simulated lots include means
  outside the decision set and preserve upside/downside tradeoffs. See
  [ROBUST_POLICY.md](ROBUST_POLICY.md); this is not a realised-loss guarantee.
- Inspection-effort comparison implemented: three fixed per-stratum sample
  budgets share simulated lots and outcomes, with paired prediction/return
  contrasts, inspection-cost sensitivity and incremental break-even prices.
  See [INSPECTION_BUDGET.md](INSPECTION_BUDGET.md). This comparison assumes
  nondestructive checks; dependence, empirical costs and adaptive plans remain open.
- Destructive inspection accounting implemented: a pre-cutoff removal ledger
  updates eligible mass and future holding costs. A paired study after one
  fixed plan distinguishes fitted value corrections from realised decision
  gains. See [INSPECTION_REMOVALS.md](INSPECTION_REMOVALS.md).
- Destructive plan comparison implemented: three fixed sampling budgets and
  no-inspection sale benchmarks share one finite fruit population per lot.
  Returns include holding from harvest, actual removed fruit and labour;
  paired contrasts retain negative findings. See
  [INSPECTION_PLAN_VALUE.md](INSPECTION_PLAN_VALUE.md). Optimal sampling designs
  and empirical inspection economics remain open.
- Historical baseline implemented: a frozen stratum-specific marginal Weibull
  fit uses completed historical lots, with calendar and lot-ID separation.
  Fresh target lots compare deployment returns and future inventory forecasts;
  archive-acquisition costs and variation across training archives are excluded.
  See [HISTORICAL_BASELINE.md](HISTORICAL_BASELINE.md). Empirical distribution shift,
  historical-data economics and empirical validation remain open.
- Training-archive variation implemented as a separate study: nested 10/100-lot
  archives are refitted across independent train/test repetitions, with shared
  target outcomes within each repetition. Paired repetition-bootstrap intervals
  cover expected deployment returns and future prediction scores under a fixed
  generator. See [ARCHIVE_UNCERTAINTY.md](ARCHIVE_UNCERTAINTY.md). These intervals
  include archive and finite-test-panel variation; their separate variance
  components, acquisition economics and empirical learning curves remain open.
- Historical-policy shift sensitivity implemented: target lifetimes are scaled
  from harvest while historical data, fitted curves and sale dates stay fixed.
  Paired outcomes across declared shorter/unchanged/longer scenarios quantify
  returns, downside, forecast scores and inventory bias, with independent
  train/test repetition intervals. See [HISTORICAL_SHIFT.md](HISTORICAL_SHIFT.md).
  Empirical shift frequency, detection, adaptation, covariate-dependent shifts
  and uncertainty in prices or grading remain open.
- Survival-scenario decision rule implemented: minimise worst fitted regret
  across a fixed set of historical-curve scale multipliers. Fresh independent
  train/test repetitions compare returns and downside with the historical rule
  and immediate sale, including shifts outside the decision set. See
  [SURVIVAL_REGRET.md](SURVIVAL_REGRET.md). Lower fitted regret does not guarantee
  lower realised loss; negative findings are retained. Empirical scenario sets,
  continuous uncertainty sets and adaptive decisions remain open.
- Further economic sensitivity: delivery delays, per-kg holding cost,
  grade-specific errors, transaction costs and buyer capacities.
- Decision uncertainty: bootstrap by *harvest lot* when empirical replicated
  lots exist, plus price/process scenario simulation. The prototype's
  parametric binomial bootstrap does not substitute for these tests.

## Release criteria for an empirical claim

Do not promote this study as validated until source provenance and acceptance
criteria are documented, tests pass, holdout predictions are calibrated and
observed decisions outperform prespecified operational benchmarks under a
transparent cost ledger. Negative findings must be preserved.
