# Architecture

## System boundary

The system receives daily store-product observations and emits an order recommendation together with forecast uncertainty, decision diagnostics, and monitoring signals.

```mermaid
flowchart LR
    A[POS, stock, waste, product and promotion data] --> B[dbt data contracts]
    B --> C[Feature pipeline]
    C --> D[Quantile forecaster]
    D --> E[Conformal calibrator]
    E --> F[Ordering policy]
    F --> G[Order recommendation]
    G --> H[Inventory simulator and backtest]
    H --> I[Forecast and operational monitoring]
```

## Component boundaries

### Data contract

The minimum grain is one row per `date × store_id × product_id`. The validation layer rejects duplicate keys, negative demand, invalid shelf life, invalid lead time, and missing required values.

### Forecasting

The first implementation fits one gradient-boosting model per quantile. This is transparent and robust for heterogeneous tabular data. The interface is model-agnostic, allowing LightGBM distributional objectives, GAMLSS-type models, neural temporal models, or hierarchical approaches later.

### Calibration

The calibration set follows the training period and precedes the test period. A split-conformal correction expands the central interval using out-of-sample conformity scores. Coverage is measured again on the untouched test period.

### Inventory state

Inventory is represented as FIFO cohorts with remaining shelf life. Deliveries enter after a product-specific lead time. Physical stock is reduced by sales, expiry, and stochastic shrinkage. The policy observes a noisy stock record rather than the true state.

The simulator records the daily event sequence and can enforce case packs, minimum order quantities, storage capacity, supplier fill rates, and stochastic lead-time extensions. Default controls preserve the unconstrained local demo.

### Decision policy

The policy receives a forecast target, observed stock, stock in transit, lead time, and shelf life. The default policy orders up to a demand quantile. The economic policy derives the quantile from the newsvendor critical fractile.

### Evaluation

Statistical evaluation and policy evaluation are kept separate. A model can improve pinball loss yet produce worse orders because errors occur in costly products, near capacity constraints, or in the wrong tail. The final comparison therefore prioritises decision cost and service/waste trade-offs.

## Production deployment pattern

1. dbt materialises validated daily features in BigQuery.
2. Airflow launches a Cloud Run Job for training or batch scoring.
3. Model artefacts and manifests are registered in a model registry or object storage.
4. A policy job writes recommendations and explanations to BigQuery.
5. Monitoring compares input distributions, interval coverage after outcomes arrive, and operational policy KPIs.
6. Failed data contracts or severe undercoverage block recommendation publication.

## Reliability principles

- Time-based tests only; no random train/test split.
- Idempotent jobs partitioned by decision date.
- Immutable run manifests with configuration and data boundaries.
- Explicit fallback policy when models or features are unavailable.
- Monitoring at global, retailer, store, department, and product levels.
- Shadow evaluation before changing the active ordering policy.
