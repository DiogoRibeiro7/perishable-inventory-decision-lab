# Synthetic out-of-time policy evaluation

## Question and comparator

Does modelling commercial survival separately by harvest-time maturity stratum
improve future quality prediction and realised sale revenue relative to assuming
one shared survival curve for the entire initially saleable batch?

The treatment here is a modelling/policy choice, not an intervention on fruit.
All results are simulated, not observations from orchards, cold rooms or buyers.
Do not infer that stratification improves real-world revenue from this experiment.

## Prospective experiment

For each independent synthetic 1,000 kg harvest lot:

1. Sample two distinct, hidden Weibull deterioration processes for initially
   eligible advanced and intermediate fruit. Their total eligible mass is
   850 kg, but the mass split varies by lot. A further 150 kg of initially
   immature fruit is never counted as fresh-market saleable.
2. Simulate fresh, cross-sectional quality inspection samples at days 3, 6,
   9 and 12, with 180 fruit per eligible group and inspection. Grade labels
   and inventory weights are fixed before deterioration outcomes.
3. At the day-12 information cut-off, fit (a) separate Weibull curves from
   each group's binomial counts and (b) a deliberately restricted common
   Weibull curve. The latter uses inventory-mass standardisation to prevent
   the sampling design from overweighting a small maturity group.
4. Present both models with exactly the same entirely hypothetical known
   grade-specific daily price schedule, storage cost and two-day delivery
   lag. Each policy selects one sale day between days 12 and 28, inclusive.
   Compare these policies against immediate sale and an inaccessible oracle
   which knows the generating survival parameters.
5. After choices are fixed, draw held-out, independent cross-sectional
   inspections at days 16, 20 and 24, as well as individual latent failure
   times used to score realised revenue. Every policy on the same lot uses
   *the same* prices and potential fruit outcomes, regardless of when it sells.
6. Repeat with independent lots. Bootstrap entire paired lot differences for
   illustrative 95% percentile intervals; do not independently resample
   different policies or individual fruit as if they were independent lots.

No held-out count or realised fruit failure time enters either fitted policy.
The oracle is included only to show a reference policy using information not
available in real decisions. It maximises true *expected* value, not the
value conditional on all realised future fruit failure times, so its realised
payoff need not be the largest on any particular simulated lot.

## Estimands and decision rules

For an initially eligible group \(g\), the fitted survival probability is
\(\hat S_g(t)\). Individual-level proper scores computed from held-out
aggregate counts are

\[
\mathrm{Brier}=\frac{\sum_{g,t}w_{g,t}\{y_{g,t}(1-\hat S_g(t))^2+
(n_{g,t}-y_{g,t})\hat S_g(t)^2\}}{\sum_{g,t}w_{g,t}n_{g,t}}
\]

and the corresponding binomial log loss per fruit (using clipped fitted
probabilities solely for numerical stability). These are not the squared
errors of empirical fractions: that would discard individual-fruit
uncertainty and distort the comparison.

For each inspection day \(t\), let eligible mass share be
\(a_g=M_g/\sum_hM_h\) and total inspected number be
\(N_t=\sum_hn_{h,t}\). The weight assigned to an observation from
group \(g\) is \(w_{g,t}=a_gN_t/n_{g,t}\), so each day's contribution is
standardised to the original mass shares. The same weights define the
pooled model's binomial pseudo-likelihood.

Scoring existing predictions accepts a single future inspection day and
all-pass or all-fail counts, including a stratum with no observed deterioration
or no remaining acceptable fruit. These are valid evaluation outcomes, not
grounds for dropping a lot. Fitting retains its separate requirements of at
least three distinct inspection days and both outcomes per eligible stratum.

Inventory standardisation requires exactly one row for every eligible stratum
on each inspection day, with positive integer sample sizes. Unequal sample
sizes are allowed. Missing strata are rejected explicitly: the implemented
weights cannot reconstruct their unobserved outcomes, and silently omitting
them would change the population represented by the score or pooled fit.
All scoring days must remain strictly after the decision cut-off.

Realised value of policy \(\pi\), choosing \(d_\pi\), is

\[
R_\pi=\sum_g M_g\left(\frac{1}{N_g}\sum_{i=1}^{N_g}
\mathbf{1}\{T_{gi}>d_\pi+L\}\right)p_g(d_\pi)
-c\left(\sum_g M_g\right)(d_\pi-d_0+L).
\]

Equal mass is assumed for synthetic fruit within each stratum. Our main
comparison is the mean paired \(R_{\rm stratified}-R_{\rm pooled}\), with
stratified minus immediate as a secondary economic contrast. Predictive gains
are reported as pooled minus stratified proper score, so positive indicates
better stratified prediction. We report the fraction of lots with distinct
selected days. A small predictive gain need not yield an economic gain.

## Reproduction

All dependencies are included with base R. From this folder:

```bash
Rscript tests/test_model.R
Rscript tests/test_evaluation.R
Rscript scripts/run_policy_evaluation.R
# Optionally vary the number of simulated independent lots:
Rscript scripts/run_policy_evaluation.R 200
```

The script fixes the simulation RNG seed to `20261022` and the lot-bootstrap
seed to `9187`; it prints descriptive results and paired confidence intervals.
The code imposes no requirement that the maturity-aware strategy wins.
Differences may be negative, intervals may overlap zero, and tied optimal
sale days count as no policy disagreement.

Weibull fitting uses bounded L-BFGS-B with a bounded PORT fallback and
deterministic alternative starts for rare numerical non-convergence. If these
attempts all fail, the experiment stops and reports the affected lot; it does
not discard difficult lots and thereby bias the policy comparison.

## Scope and threats to validity

- The generator uses Weibull hazards, which gives the model family an
  artificial advantage. We do not test model misspecification, shared
  spoilage shocks, fruit size–survival dependence or grading mistakes.
- All price schedules are random hypothetical paths *known at decision time*;
  real price forecasts are uncertain. Transaction fees, split sales, buyer
  capacity and alternative processing outlets are omitted.
  The separate [price-error study](PRICE_SENSITIVITY.md) holds these fitted
  decisions fixed and scores shared biased/unbiased realised price paths.
- Inspecting oranges removes no material quantity in this toy world, and
  inspection outcomes are independently drawn from a static synthetic
  population rather than a finite warehouse with withdrawals.
- Repeated synthetic lots let us assess numerical variation in this
  specified generator only. They do not measure generalisation to new
  orchards, cultivars, storage conditions, years or markets.
- Survival here means meeting a prespecified commercial quality threshold,
  not being microbiologically safe to eat.

Before field claims, pre-register decisions and commercial acceptance
criteria, sample actual lots, assess calibration and conduct lot-blocked
out-of-sample validation with historical prices and full cost accounting.
See [PROTOCOL.md](PROTOCOL.md) for measurement and release requirements.
