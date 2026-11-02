list(n_lots = 200, simulation_seed = 20261028L, label_seed = 20261029L,
    outcome_seed = 20261030L, bootstrap_seed = 9190L, n_boot = 1000L,
    decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
    storage_eur_per_kg_day = 0.001, training_per_group = 180L,
    holdout_per_group = 250L, scenarios = structure(list(scenario = c("perfect",
    "balanced_errors", "more_false_accepts", "more_false_rejects"
    ), sensitivity = c(1, 0.9, 0.95, 0.8), specificity = c(1,
    0.9, 0.8, 0.95)), class = "data.frame", row.names = c(NA,
    -4L)), r_version = "R version 4.5.1 (2025-06-13 ucrt)", rng_kind = c("Mersenne-Twister",
    "Inversion", "Rejection"))
