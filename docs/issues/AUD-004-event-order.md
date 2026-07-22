# High: Configure Simulator Event Order

## Problem

Expiry, receiving, shrinkage, sales, and order placement order can materially change waste and fill rate for short shelf-life products.

## Evidence

- `src/perishable_lab/inventory/simulator.py`
- `tests/test_inventory.py`
- `docs/MODELLING_DECISIONS.md`

## Required Work

- Add named simulator event-order modes.
- Preserve the current sequence as the default.
- Record the selected mode in daily outputs and policy summaries.
- Document which retail operating assumptions each mode represents.

## Acceptance Criteria

- One-day shelf-life fixtures produce expected outcomes under each mode.
- Existing simulator conservation tests still pass.
- Default mode preserves current demo behavior.
