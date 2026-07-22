# Modelling Decisions

## Why forecast a distribution?

Fresh-food ordering is asymmetric. Underforecasting creates lost sales and poor availability; overforecasting creates expiry and disposal. A point forecast cannot represent the probability mass needed to choose a service level or an economic critical fractile.

## Why quantile models first?

Quantile regression is a practical baseline for messy retail panels. It avoids a rigid parametric demand distribution, supports zero-heavy and overdispersed demand, and directly supplies the tails used by ordering policies. Separate models may cross, so predictions are projected into monotonic order before calibration.

## Why conformal calibration?

A probabilistic model can have useful ranking but poor marginal coverage. Split conformal calibration provides a model-agnostic correction on a temporally later calibration window. It does not guarantee conditional coverage for every product or store, so the monitoring plan also computes segmented coverage.

## Newsvendor interpretation

For a one-period approximation, the economically optimal quantile is

\[
q^* = \frac{C_u}{C_u + C_o},
\]

where `C_u` is the cost of underage and `C_o` is the cost of overage. The demo approximates underage with lost contribution margin and overage with acquisition plus disposal cost. In production, these values should also include substitution, customer retention, markdown recovery, handling, and contractual constraints.

## Perishability

A cohort simulator is used rather than a single inventory number. This allows the policy to be evaluated against expiry dynamics. The initial policy uses total observed stock; a stronger policy would use the age profile and optimise depletion-aware replenishment.

## Inventory uncertainty

The simulator maintains true physical stock but exposes a noisy observation to the policy. This separates demand uncertainty from state uncertainty and creates a path toward Bayesian stock estimation or a partially observable Markov decision process.

## Known limitations

- One-day demand distributions approximate lead-time demand by a multiplier.
- No explicit substitution or cannibalisation between similar products.
- No minimum order quantities, case packs, capacity, supplier calendars, or order cut-offs.
- No markdown pricing or dynamic disposal decisions.
- Calibration is global rather than hierarchical or segment-conditional.
- Synthetic demand is useful for engineering tests but cannot establish real commercial lift.

These limitations are documented because production judgement includes knowing where a model should not be trusted.
