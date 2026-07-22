# Shelf-Life Model Card

## Purpose

The shelf-life layer provides a remaining sellable-life distribution for inventory simulation and waste-aware ordering. It separates product-master shelf-life assumptions from batch-level observations such as receipt date, pack date, expiry date, quality rejection, markdown, and recorded waste.

## Methods

- `MasterDataShelfLifeModel`: deterministic baseline from product master data.
- `EmpiricalShelfLifeModel`: product, supplier, and season distribution from uncensored batch observations.
- `ConservativeShelfLifeFallback`: declared fallback for sparse or conflicting evidence.

Right-censored batches are retained in diagnostics but are not treated as observed expiry events. Disappearance is not interpreted as expiry unless sales, transfers, markdowns, damage, and unrecorded shrinkage are accounted for upstream.

## Ordering Use

Ordering code should consume `ShelfLifeDistribution` metadata or an explicit conservative fallback source. Fixed constants should be treated as the deterministic master-data baseline, not as undocumented truth.

## Evaluation

Validation should report survival calibration, Brier score, remaining-life interval coverage, waste prediction error, and policy cost impact by product, supplier, family, season, and delivery condition.
