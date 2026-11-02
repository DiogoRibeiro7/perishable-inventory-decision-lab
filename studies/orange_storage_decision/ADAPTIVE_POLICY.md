# Sequential inspection versus committing to a sale date

## Question

At day 12, is it worth waiting until day 16 and paying for another representative
quality inspection, **when the result can change the selling date**? The earlier
experiments fix inspection plans before their observations arrive. This experiment
adds one contingent action, with no use of observations from the future.

## Decision model

The initially fresh-market-eligible inventory has two maturity strata. Before
examining a target lot, specify a small library of three commercial-survival
hypotheses (`short`, `typical`, `long`) and a prior probability for each. In
hypothesis \(h\), grade \(g\) follows Weibull survival \(S_{hg}(t)\). The
observed cohort masses and initial eligibility are identical across hypotheses;
only lifetime scales differ. The hypothesis set is **not** estimated using hidden
target-lot failure times or postdecision inspections.

Under independent, representative, nondestructive perfect-label inspections,
\(Y_{g,t}\mid h\sim\mathrm{Binomial}(n_{g,t}, S_{hg}(t))\). Given all inspection
counts available by day 12, update the prior using Bayes' rule:

\[
w_h^{12} \propto w_h^0\prod_{g,t\leq12}
  {n_{g,t}\choose y_{g,t}}S_{hg}(t)^{y_{g,t}}
  (1-S_{hg}(t))^{n_{g,t}-y_{g,t}}.
\]

For each available sale day \(d\), the existing `expected_value_grid()` gives
\(V_h(d)\), including a two-day delivery lag, grading at delivery and holding
costs **from day 12**. The day-12 choice is either:

1. **Commit:** Select a fixed date \(d\geq12\) maximizing
   \(F=\max_d\sum_h w_h^{12}V_h(d)\). This includes selling immediately.
2. **Inspect:** Wait until day 16, inspect \(n\) fruit per eligible stratum,
   update the posterior from those **new** counts, then choose a sale date
   \(d\geq16\). Its day-12 expected net value is

   \[
   I=\sum_{\mathbf y}P(\mathbf y\mid\mathcal D_{12})
       \max_{d\geq16}\sum_h w_h^{16}(\mathbf y)V_h(d)
      -nG c_{\mathrm{check}},
   \]

   where \(G\) is the number of eligible strata. The inspection costs
   \(c_{\mathrm{check}}\) per checked fruit; holding costs are *already* inside
   \(V_h(d)\), so they are not charged again.

The policy orders the inspection only if \(I>F\), breaking ties in favour of
commitment. If it commits, it **cannot** use day-16 observations to revise that
sale day. The final date after inspection is selected only when its counts
actually become available. This is an exact, one-step finite-scenario
value-of-information calculation, **not** a general multi-period POMDP solver.
The reported inspection-option gain \(I-F\) includes the opportunity cost of
waiting until day 16 and can be negative; it is not pure information value
with a fixed common action set.
For the default two eligible grades and eight checks each, all \(9^2=81\)
joint possible follow-up count vectors are explicitly enumerated. Larger
configurations are bounded to 5,000 outcomes.

## Prospective paired experiment

- One synthetic lot has 850 kg of initially saleable fruit split between
  `advanced` and `intermediate`, plus 150 kg excluded as initially immature.
- Survival shapes are fixed at 2.2 and 1.8 by grade; base scales are 18 and
  36 days, multiplied by 0.70/1.00/1.35 under the short/typical/long
  scenarios. Every target lot draws one latent scenario from the known prior
  (0.3/0.4/0.3). This is a deliberately *correctly specified* finite prior.
- Day-6 and day-12 observations have six checks per eligible grade per date.
  Day-16 follow-up has eight checks per eligible grade and costs EUR 0.02 per
  check. All checks are assumed nondestructive; their hypothetical label
  samples are independent conditional on the latent scenario.
- The same exogenous, hypothetical price path over days 12–28 is supplied to
  every policy on that lot. Storage costs EUR 0.001 per eligible kg per day;
  delivery lag is two days.
- Compare adaptive choice against (a) committing to the best fixed date on day
  12, (b) immediate sale on day 12, and (c) always inspecting on day 16 before
  choosing a date. The fixed policy and immediate sale have no day-16 labour
  costs. Labour is paid only when the adaptive policy actually inspects; the
  always-inspect policy pays it on every lot.
- Each comparison uses **identical** fruit-level lifetimes, inventory and prices
  on the same target lot. The hypothetical follow-up counts are drawn only
  **after** the day-12 plan is frozen. They are observable to the adaptive
  policy only if it chose inspection, and to the always-inspect comparator.
- Report all gains (including negatives) and paired 95% percentile bootstrap
  intervals resampling independent *lots*, never individual fruits or policy
  records. The script fixes both simulation and bootstrap seeds.

The shared day-6/day-12 inspection budget is a sunk information source in all
arms. Its cost is omitted equally; including that common cost would not change
paired gains. Values start on day 12, so they do not imply full-season profit.

## Reproduce

Requires base R. From `studies/orange_storage_decision/`:

```sh
Rscript tests/test_adaptive_policy.R
Rscript scripts/run_adaptive_policy.R 200
```

The script writes per-lot records, paired summaries, fixed settings and a short
results note under `results/adaptive_policy/` (or a second-argument directory).
The CI exercises a smaller experiment in a temporary directory.

## Boundaries and next experiments

The result is conditional on the finite hypothesis set being correct, on fixed
known future prices, representative independent binary assessments, and
perfect nondestructive inspection. Real maturity measurement can be noisy,
destructive, clustered and mass-dependent. Scenario weights are supplied, not
calibrated on an independent archive; a real test would estimate them from
historical lots and evaluate prospectively under shelf-life and price shift.
Destructive sampling would require reducing future saleable inventory and
tracking holding cost from each removal, as in the separate inspection-removal
extension. Neither operational adoption nor empirical profit improvements are
supported by this synthetic study.
