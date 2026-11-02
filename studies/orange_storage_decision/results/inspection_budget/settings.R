list(n_lots = 200L, training_seed = 20261106L, outcome_seed = 20261107L,
    bootstrap_seed = 9213L, n_boot = 1000L, budgets = c(30L,
    90L, 180L), costs_eur_per_inspection = c(0, 0.02, 0.05, 0.1
    ), sensitivity = 0.9, specificity = 0.9, decision_day = 12L,
    last_sale_day = 28L, delivery_lag_days = 2L, storage_eur_per_kg_day = 0.001,
    training_days = c(3L, 6L, 9L, 12L), holdout_per_group = 250L,
    scenarios = structure(list(scenario = c("common_shape", "nearby_shapes",
    "different_shapes"), advanced_shape = c(2, 2.2, 1), intermediate_shape = c(2,
    1.8, 3.5), common_jitter = c(TRUE, FALSE, FALSE)), class = "data.frame", row.names = c(NA,
    -3L)), r_version = "R version 4.5.1 (2025-06-13 ucrt)", rng_kind = c("Mersenne-Twister",
    "Inversion", "Rejection"))
