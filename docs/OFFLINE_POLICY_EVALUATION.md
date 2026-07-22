# Offline Policy Evaluation

## Principle

Offline evaluation must distinguish replayable outcomes from counterfactual claims. Historical stock, sales, waste, and lost sales were shaped by the historical ordering policy, so a new policy may request actions in states that have weak or no historical support.

## Supported Outputs

- Deterministic replay for policy-invariant outcomes.
- Simulator-based scenario results when calibrated uncertainty is available.
- IPW and doubly robust estimates only when propensities and overlap are adequate.
- Bounds or `not_identifiable` when overlap, hidden demand, or hidden inventory assumptions are too weak.

## Required Diagnostics

Reports include action overlap, effective sample size, maximum weight, minimum propensity, estimator variance, outcome label, and an assumption checklist.
