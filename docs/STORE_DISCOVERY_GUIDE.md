# Store Operations Discovery Guide

This guide turns operational observations into testable data and product changes. Staff are not asked to validate mathematical concepts. Uncertainty is translated into choices such as review, fallback, confidence bands, and explanation needs.

## Interview Structure

For each workflow capture:

- Actor and decision.
- Information visible at the time.
- Current tool or workaround.
- Frequency and operational cost.
- Exceptions and edge cases.
- Data generated or missing.
- What a good recommendation would need to explain.

## Store Staff

| Area | Questions |
| --- | --- |
| Order cutoffs | What happens in the final hour before orders are locked? Which late signals matter most? |
| Delivery windows | When do deliveries arrive versus when shelves need to be filled? What happens when delivery is late or partial? |
| Shelf filling | Who decides what reaches the shelf first? Which products stay in back-room stock? |
| Back-room stock | Where can stock exist outside the shelf count, and when is it checked? |
| Waste recording | Which wasted items are recorded immediately, later, or not at all? |
| Stock counts | What triggers a count, and how are count differences handled? |
| Overrides | When do you change a suggested quantity, and what explanation would make that change easier to trust? |
| Escalation | What issue makes you call support or stop using a recommendation? |

## Customer Success

| Area | Questions |
| --- | --- |
| Support patterns | Which store issues create tickets, and how are repeated issues grouped? |
| System trust | What signs make stores stop trusting recommendations for a category? |
| Rollout readiness | Which teams need communication before changing the review workflow? |
| Failure recovery | What must be true before stores accept that an issue is resolved? |

## Buyers

| Area | Questions |
| --- | --- |
| Promotions | Which promotion or display changes are known before the order cutoff? |
| Substitutions | Which products substitute for each other when one item is unavailable? |
| Case packs | Which supplier or category rules create order-size constraints? |
| Local events | What local demand drivers are planned outside central systems? |

## Engineering

| Area | Questions |
| --- | --- |
| Source latency | Which source tables can arrive late or be restated after recommendations are produced? |
| Constraints | Where are case-pack, storage, supplier, and shelf-life constraints maintained and versioned? |
| Auditability | Which identifiers let us replay the exact recommendation shown to a store? |
| Monitoring | Which signals indicate data, publication, or workflow failure before stores are affected? |

## Blame-Safe Facilitation

Frame errors as workflow or data-design gaps. Do not ask who made a mistake; ask what information was missing, late, hard to see, or hard to act on. Separate local exceptions from repeated patterns before proposing product or model changes.
