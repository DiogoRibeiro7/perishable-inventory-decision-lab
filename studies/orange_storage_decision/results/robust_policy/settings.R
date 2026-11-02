list(n_lots = 200, simulation_seed = 20261024L, price_seed = 20261025L,
    bootstrap_seed = 9188L, n_boot = 1000L, decision_ratios = c(0.6,
    0.8, 1), decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
    storage_eur_per_kg_day = 0.001, scenarios = structure(list(
        scenario = c("perfect_forecast", "unbiased_noise", "mean_20pct_lower",
        "mean_40pct_lower", "mean_60pct_lower", "mean_20pct_higher"
        ), terminal_mean_multiplier = c(1, 1, 0.8, 0.6, 0.4,
        1.2), terminal_log_sd = c(0, 0.2, 0.2, 0.2, 0.2, 0.2)), row.names = c(NA,
    -6L), class = "data.frame"), r_version = "R version 4.5.1 (2025-06-13 ucrt)",
    rng_kind = c("Mersenne-Twister", "Inversion", "Rejection"
    ))
