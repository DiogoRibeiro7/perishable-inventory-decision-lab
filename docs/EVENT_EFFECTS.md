# Price, Promotion, Calendar, And Event Effects

## Data Semantics

The event feature layer separates planned promotion, published promotion, executed promotion, realised discount, display compliance, cancellation status, and correction time. A field is usable for a decision only when its `known_at` timestamp is no later than the order cutoff for the scored date.

Future plans can be used when they were already known by the cutoff. Retrospective campaign corrections, realised sales outcomes, and end-of-campaign status are not used for earlier scoring rows.

## Feature Families

- Regular and planned price.
- Planned discount depth.
- Promotion type, status, duration, and event window.
- Pre-promotion, active-promotion, post-promotion, and normal windows.
- Weekday, season, public holiday, school holiday, payday, and store closure.
- Interactions with baseline velocity and shelf life when those columns are available.

## Fallback Rules

Missing plans become `promotion_type = unknown`, `promotion_status = unknown`, `discount_depth = 0`, and `event_window = normal`. Cancelled promotions remain explicit through `cancelled_promotion = true` and are not treated as active demand shocks.

## Causal Caution

Promotion features are predictive controls, not causal proof. Incrementality requires a separate design that addresses confounding, selection into promotion, cannibalisation, forward buying, substitution, and limited overlap.
