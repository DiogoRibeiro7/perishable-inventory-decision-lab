list(n_lots = 200, simulation_seed = 20261022L, price_seed = 20261023L,
    bootstrap_seed = 9187L, n_boot = 1000L, decision_day = 12L,
    last_sale_day = 28L, delivery_lag_days = 2L, scenarios = structure(list(
        scenario = c("perfect_forecast", "unbiased_noise", "mean_20pct_lower",
        "mean_40pct_lower"), terminal_mean_multiplier = c(1,
        1, 0.8, 0.6), terminal_log_sd = c(0, 0.2, 0.2, 0.2)), class = "data.frame", row.names = c(NA,
    -4L)), r_version = "R version 4.5.1 (2025-06-13 ucrt)", rng_kind = c("Mersenne-Twister",
    "Inversion", "Rejection"))
