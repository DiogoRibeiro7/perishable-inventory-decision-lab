# Advanced Probabilistic Research Track

The research track asks whether a more expressive probabilistic forecaster improves replenishment decisions enough to justify operational complexity. It deliberately keeps the existing quantile boosting baseline in every comparison table.

Run a comparison on canonical daily rows with:

```bash
poetry run perishable-lab research-comparison input.csv --output-dir artifacts/research-comparison
```

## Candidate Selection

Only two candidates are admitted initially:

| Model | Reason | Main risk |
| --- | --- | --- |
| Negative-binomial quantile forecaster | Directly targets zero-heavy and overdispersed count demand. | Parametric tails can be wrong under promotions or censored sales. |
| Residual scenario ensemble | Tests scenario generation and tail spread without a heavy temporal stack. | Residual exchangeability can fail under structural breaks. |

Deferred families:

- Deep global temporal models. These add serialization, latency, feature-parity, and fallback complexity before baseline failure evidence proves they are needed.
- Bayesian hierarchical count models. These are attractive for sparse cohorts, but sampling and operational workflow costs are not justified until sparse-cohort failures dominate the error budget.

## Experimental Discipline

Every model uses:

- identical chronological train, calibration, and test windows;
- the same cutoff-safe feature table;
- fixed seeds;
- the same quantile columns;
- the same policy proxy evaluation;
- validation-only calibration and no tuning on the final test period.

The manifest records experiment id, split endpoints, feature columns, selected models, baseline model, seed, and quantiles.

## Metrics

Forecast metrics:

- pinball loss by quantile;
- empirical interval coverage;
- mean interval width;
- approximate CRPS.

Decision metrics:

- order quantity;
- fulfilled units;
- lost-sales units;
- waste units;
- proxy operating cost.

Deployment decisions use paired cost deltas with block bootstrap uncertainty. A lower average forecast loss is not sufficient.

## Ablations

The implementation writes an ablation table covering:

- full feature run;
- fit time;
- prediction latency;
- finite-prediction fallback rate.

These are intentionally basic but force the comparison to include compute, stability, and fallback behavior.

## Keep or Reject Rule

A candidate is kept only when paired operating cost improves beyond the configured threshold and the paired interval is fully below zero. Otherwise the decision is `reject_for_now`.

The expected outcome is often rejection. That is acceptable: the objective is disciplined model selection, not novelty.
