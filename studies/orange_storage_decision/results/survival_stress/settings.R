list(n_lots = 200, simulation_seed = 20261026L, inspection_seed = 20261027L,
    bootstrap_seed = 9189L, n_boot = 1000L, decision_day = 12L,
    change_day = 12L, delivery_lag_days = 2L, holdout_days = c(16L,
    20L, 24L), holdout_per_group = 250L, storage_eur_per_kg_day = 0.001,
    price_decision_ratios = c(0.6, 0.8, 1), scenarios = structure(list(
        scenario = c("unchanged", "slower", "faster", "double_hazard"
        ), hazard_multiplier = c(1, 0.5, 1.5, 2)), class = "data.frame", row.names = c(NA,
    -4L)), r_version = "R version 4.5.1 (2025-06-13 ucrt)", rng_kind = c("Mersenne-Twister",
    "Inversion", "Rejection"))
