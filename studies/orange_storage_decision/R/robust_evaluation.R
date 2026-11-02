# Source model, sampling, evaluation, simulation, price_sensitivity and
# robust_policy first. Decision scenarios and evaluation scenarios are separate.

robust_evaluation_scenarios <- function() {
  rbind(default_price_scenarios(), data.frame(
    scenario = c("mean_60pct_lower", "mean_20pct_higher"),
    terminal_mean_multiplier = c(0.4, 1.2), terminal_log_sd = 0.2
  ))
}

#' Evaluate a fixed minimax-regret policy on fresh paired synthetic lots.
#' @param n_lots Independent lots, at least two.
#' @param simulation_seed Fresh seed, distinct from the exploratory price study.
#' @param price_seed Independent price-innovation seed; resets caller RNG.
#' @param decision_ratios Finite assumed mean-price set, fixed before evaluation.
#' @param scenarios Realised-price settings, never supplied to the policy.
#' @return One row per lot/scenario, with fixed dates and realised net returns.
run_robust_policy_experiment <- function(n_lots = 200L,
                                        simulation_seed = 20261024L,
                                        price_seed = 20261025L,
                                        decision_ratios = c(0.6, 0.8, 1),
                                        scenarios = robust_evaluation_scenarios()) {
  validate_price_scenarios(scenarios)
  assert_nonnegative_scalar(n_lots, "n_lots", integer = TRUE)
  assert_nonnegative_scalar(simulation_seed, "simulation_seed", integer = TRUE)
  assert_nonnegative_scalar(price_seed, "price_seed", integer = TRUE)
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  policy <- function(cohorts, prices, cost, day, lag) {
    paths <- price_mean_scenarios(prices, cohorts, day, decision_ratios)
    minimax_regret_sale(cohorts, paths, cost, day, lag)$decision$sale_day
  }
  set.seed(simulation_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    tryCatch(simulate_policy_lot(id, additional_policy = policy),
             error = function(error) {
               stop(sprintf("synthetic lot %d failed: %s", id,
                            conditionMessage(error)), call. = FALSE)
             })
  })
  set.seed(price_seed)
  rows <- lapply(lots, function(lot) {
    innovations <- stats::rnorm(length(unique(lot$prices$day)) - 1L)
    do.call(rbind, lapply(seq_len(nrow(scenarios)), function(i) {
      setting <- scenarios[i, , drop = FALSE]
      actual <- apply_price_error(lot$prices, lot$truth, lot$decision_day,
                                   setting$terminal_mean_multiplier,
                                   setting$terminal_log_sd, innovations)
      baseline <- score_policy_lot(lot, actual)
      kept <- c("lot_id", "sale_day_stratified", "sale_day_pooled",
                "realised_stratified_eur", "realised_pooled_eur", "realised_immediate_eur")
      row <- baseline[kept]
      row$sale_day_robust <- lot$additional_day
      row$realised_robust_eur <- realised_sale_value(
        lot$additional_day, lot$truth, actual, lot$lifetimes,
        lot$storage_eur_per_kg_day, lot$decision_day, lot$delivery_lag_days
      )
      cbind(setting, row, row.names = NULL)
    }))
  })
  result <- do.call(rbind, rows)
  rownames(result) <- NULL
  result
}

#' Summarise paired returns and downside; caller controls bootstrap RNG.
#' @param records Complete paired output of run_robust_policy_experiment().
#' @param n_boot Whole-lot bootstrap resamples per mean contrast.
#' @return One row per evaluation scenario; marginal intervals, descriptive risk.
summarize_robust_policy <- function(records, n_boot = 1000L) {
  numeric_fields <- c("terminal_mean_multiplier", "terminal_log_sd", "lot_id",
                      "sale_day_stratified", "sale_day_pooled", "sale_day_robust",
                      "realised_stratified_eur", "realised_pooled_eur",
                      "realised_immediate_eur", "realised_robust_eur")
  if (!is.data.frame(records) ||
      !all(c("scenario", numeric_fields) %in% names(records)) ||
      any(!vapply(records[numeric_fields], function(x) {
        is.numeric(x) && all(is.finite(x))
      }, logical(1)))) {
    stop("records need finite numeric dates, lot IDs, settings and returns", call. = FALSE)
  }
  settings <- unique(records[c("scenario", "terminal_mean_multiplier", "terminal_log_sd")])
  validate_price_scenarios(settings)
  if (anyDuplicated(records[c("scenario", "lot_id")]) ||
      length(unique(records$lot_id)) < 2L ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records need complete paired lot/scenario measurements", call. = FALSE)
  }
  fixed <- c("sale_day_stratified", "sale_day_pooled", "sale_day_robust",
             "realised_immediate_eur")
  for (id in unique(records$lot_id)) {
    if (nrow(unique(records[records$lot_id == id, fixed])) != 1L) {
      stop("sale dates and immediate revenue must be fixed across scenarios",
           call. = FALSE)
    }
  }
  do.call(rbind, lapply(settings$scenario, function(name) {
    part <- records[records$scenario == name, ]
    row <- data.frame(scenario = name, n_lots = nrow(part),
                       mean_sale_day_robust = mean(part$sale_day_robust),
                       mean_sale_day_stratified = mean(part$sale_day_stratified))
    for (policy in c("robust", "stratified", "pooled", "immediate")) {
      values <- part[[paste0("realised_", policy, "_eur")]]
      row[[paste0("mean_", policy, "_eur")]] <- mean(values)
      if (policy != "immediate") {
        difference <- values - part$realised_immediate_eur
        row[[paste0(policy, "_below_immediate_fraction")]] <- mean(difference < 0)
        row[[paste0(policy, "_minus_immediate_p10_eur")]] <-
          unname(stats::quantile(difference, 0.1))
      }
    }
    for (baseline in c("stratified", "pooled", "immediate")) {
      interval <- paired_lot_interval(
        part$realised_robust_eur - part[[paste0("realised_", baseline, "_eur")]], n_boot
      )
      for (statistic in names(interval)) {
        row[[paste0("robust_minus_", baseline, "_", statistic, "_eur")]] <-
          unname(interval[statistic])
      }
    }
    row
  }))
}
