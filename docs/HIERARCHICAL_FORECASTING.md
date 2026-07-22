# Hierarchical Forecasting And Cold Starts

## Supported Levels

The fallback layer can use retailer, store, product, category, and store-product history. Additional columns such as region, store cluster, subcategory, product family, and supplier can be joined through `build_hierarchical_features` when their values are known as of the scoring cutoff.

The hierarchy is treated as a graph of useful grouping attributes, not as a strictly nested tree. This avoids forcing supplier, product-family, and category changes into one brittle path.

## Cold-Start States

- `unseen_product`
- `unseen_store`
- `unseen_store_product_pair`
- `insufficient_recent_history`
- `structural_change`
- `mature`

Every fallback prediction emits the selected source level, effective training sample, calibration source, contributing levels, and confidence limitations.

## Calibration And Shrinkage

Sparse local estimates can be shrunk toward parent estimates with empirical-Bayes weighting:

```text
shrunk = weight * local + (1 - weight) * parent
weight = local_sample_size / (local_sample_size + prior_strength)
```

Segment calibration should use a minimum sample threshold and fall back to broader levels when sample size is too small.

## Reporting

Launch simulations should hide early history for new entities and report bias, MAE, interval coverage, width, and policy outcomes by cold-start state. Reconciliation can use bottom-up sums when business reporting requires aggregate coherence.
