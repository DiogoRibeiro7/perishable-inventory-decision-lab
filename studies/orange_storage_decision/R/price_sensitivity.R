# Price forecast sensitivity. Source model.R, sampling.R, evaluation.R and
# simulation.R first. Decisions use forecasts; only scoring uses price errors.

default_price_scenarios <- function() {
  data.frame(
    scenario = c("perfect_forecast", "unbiased_noise",
                 "mean_20pct_lower", "mean_40pct_lower"),
    terminal_mean_multiplier = c(1, 1, 0.8, 0.6),
    terminal_log_sd = c(0, 0.2, 0.2, 0.2),
    stringsAsFactors = FALSE
  )
}

validate_price_scenarios <- function(scenarios) {
  fields <- c("scenario", "terminal_mean_multiplier", "terminal_log_sd")
  if (!is.data.frame(scenarios) || nrow(scenarios) < 1L ||
      !all(fields %in% names(scenarios)) ||
      !is.character(scenarios$scenario) || anyNA(scenarios$scenario) ||
      any(!nzchar(trimws(scenarios$scenario))) || anyDuplicated(scenarios$scenario)) {
    stop("scenarios need unique nonempty names and price-error parameters",
         call. = FALSE)
  }
  for (i in seq_len(nrow(scenarios))) {
    assert_nonnegative_scalar(scenarios$terminal_mean_multiplier[i],
                              "terminal_mean_multiplier")
    assert_nonnegative_scalar(scenarios$terminal_log_sd[i], "terminal_log_sd")
  }
  if (any(scenarios$terminal_mean_multiplier == 0)) {
    stop("terminal_mean_multiplier must be positive", call. = FALSE)
  }
  invisible(TRUE)
}

#' Apply a shared market-price error without revealing it to fitted policies.
#'
#' For elapsed fraction u of the forecast horizon, the multiplier is
#' m^u * exp(sigma * B(u) - sigma^2 * u / 2), where B is Brownian motion.
#' Its conditional mean is m^u. The decision-day quote is known exactly.
#' One multiplier is shared across grades; prices remain locked at sale.
#'
#' @param prices Complete forecast grid, starting at decision_day.
#' @param cohorts Initial inventory for validating the price grid.
#' @param decision_day Information cutoff and first quoted day.
#' @param terminal_mean_multiplier Expected actual/forecast ratio at the horizon.
#' @param terminal_log_sd Log-error standard deviation at the horizon.
#' @param innovations One standard-normal innovation per subsequent quoted day.
#'   Supply the same vector to pair scenarios. NULL draws it from the caller RNG.
#' @return Price grid with the original ordering and perturbed quotes.
apply_price_error <- function(prices, cohorts, decision_day,
                              terminal_mean_multiplier = 1,
                              terminal_log_sd = 0, innovations = NULL) {
  validate_cohorts(cohorts)
  validate_prices(prices, cohorts)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  scenario <- data.frame(scenario = "supplied",
                         terminal_mean_multiplier = terminal_mean_multiplier,
                         terminal_log_sd = terminal_log_sd)
  validate_price_scenarios(scenario)
  if (nrow(scenario) != 1L) {
    stop("price-error parameters must be scalars", call. = FALSE)
  }
  days <- sort(unique(prices$day))
  if (length(days) < 2L || days[1] != decision_day) {
    stop("prices must start at decision_day and include a later quote",
         call. = FALSE)
  }
  u <- (days - decision_day) / (max(days) - decision_day)
  if (is.null(innovations)) {
    innovations <- if (terminal_log_sd == 0) rep(0, length(days) - 1L) else
      stats::rnorm(length(days) - 1L)
  }
  if (!is.numeric(innovations) || length(innovations) != length(days) - 1L ||
      anyNA(innovations) || any(!is.finite(innovations))) {
    stop("innovations must be finite, one per future quoted day", call. = FALSE)
  }
  brownian <- c(0, cumsum(sqrt(diff(u)) * innovations))
  multiplier <- exp(log(terminal_mean_multiplier) * u +
                      terminal_log_sd * brownian - terminal_log_sd^2 * u / 2)
  realised <- prices
  realised$price_eur_per_kg <- prices$price_eur_per_kg *
    multiplier[match(prices$day, days)]
  validate_prices(realised, cohorts)
  realised
}

#' Pair price scenarios on identical independently generated harvest lots.
#'
#' All lots, fitted decisions and fruit outcomes are prepared before the price
#' RNG is started. Adding or reordering scenarios cannot change any lot or its
#' innovations. Price uncertainty never enters the selected dates or fitting.
#' The original oracle is omitted: under biased prices it is no longer an oracle.
#'
#' @param n_lots Number of independent lots, at least two.
#' @param simulation_seed Seed for the original prospective lot generator.
#' @param price_seed Separate seed for price innovations; resets caller RNG.
#' @param scenarios Named, predeclared price-error settings.
#' @return One row per lot/scenario, with paired scores and price-error impacts.
run_price_sensitivity <- function(n_lots = 200L, simulation_seed = 20261022L,
                                  price_seed = 20261023L,
                                  scenarios = default_price_scenarios()) {
  validate_price_scenarios(scenarios)
  assert_nonnegative_scalar(n_lots, "n_lots", integer = TRUE)
  assert_nonnegative_scalar(simulation_seed, "simulation_seed", integer = TRUE)
  assert_nonnegative_scalar(price_seed, "price_seed", integer = TRUE)
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  set.seed(simulation_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    tryCatch(simulate_policy_lot(id), error = function(error) {
      stop(sprintf("synthetic lot %d failed: %s", id, conditionMessage(error)),
           call. = FALSE)
    })
  })
  set.seed(price_seed)
  rows <- lapply(lots, function(lot) {
    innovations <- stats::rnorm(length(unique(lot$prices$day)) - 1L)
    baseline <- score_policy_lot(lot)
    paired <- lapply(seq_len(nrow(scenarios)), function(i) {
      setting <- scenarios[i, , drop = FALSE]
      actual <- apply_price_error(
        lot$prices, lot$truth, lot$decision_day,
        setting$terminal_mean_multiplier, setting$terminal_log_sd, innovations
      )
      scored <- score_policy_lot(lot, actual)
      scored <- scored[, !grepl("oracle", names(scored)), drop = FALSE]
      scored$price_impact_stratified_eur <- scored$realised_stratified_eur -
        baseline$realised_stratified_eur
      scored$price_impact_pooled_eur <- scored$realised_pooled_eur -
        baseline$realised_pooled_eur
      cbind(setting, scored, row.names = NULL)
    })
    do.call(rbind, paired)
  })
  result <- do.call(rbind, rows)
  rownames(result) <- NULL
  result
}

#' Summarise within-lot profit differences; caller controls bootstrap RNG.
#' @param records Paired output of run_price_sensitivity().
#' @param n_boot Number of whole-lot bootstrap resamples per contrast.
#' @return Scenario means, paired mean intervals and descriptive downside risks.
summarize_price_sensitivity <- function(records, n_boot = 1000L) {
  settings <- unique(records[c("scenario", "terminal_mean_multiplier", "terminal_log_sd")])
  validate_price_scenarios(settings)
  if (anyDuplicated(records[c("scenario", "lot_id")]) ||
      length(unique(records$lot_id)) < 2L ||
      any(!is.finite(as.matrix(records[, names(records) != "scenario"]))) ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records must contain complete finite paired lot/scenario measurements",
         call. = FALSE)
  }
  rows <- lapply(settings$scenario, function(name) {
    part <- records[records$scenario == name, , drop = FALSE]
    pooled_difference <- part$realised_stratified_eur - part$realised_pooled_eur
    immediate_difference <- part$realised_stratified_eur - part$realised_immediate_eur
    pooled_interval <- paired_lot_interval(pooled_difference, n_boot)
    immediate_interval <- paired_lot_interval(immediate_difference, n_boot)
    data.frame(
      scenario = name, n_lots = nrow(part),
      mean_stratified_eur = mean(part$realised_stratified_eur),
      mean_pooled_eur = mean(part$realised_pooled_eur),
      mean_immediate_eur = mean(part$realised_immediate_eur),
      stratified_minus_pooled_eur = unname(pooled_interval[1]),
      pooled_contrast_lower_95 = unname(pooled_interval[2]),
      pooled_contrast_upper_95 = unname(pooled_interval[3]),
      stratified_minus_immediate_eur = unname(immediate_interval[1]),
      immediate_contrast_lower_95 = unname(immediate_interval[2]),
      immediate_contrast_upper_95 = unname(immediate_interval[3]),
      stratified_below_immediate_fraction = mean(immediate_difference < 0),
      pooled_below_immediate_fraction = mean(part$realised_pooled_eur <
                                             part$realised_immediate_eur),
      stratified_minus_immediate_p10_eur = unname(stats::quantile(immediate_difference, 0.1)),
      mean_price_impact_stratified_eur = mean(part$price_impact_stratified_eur),
      mean_price_impact_pooled_eur = mean(part$price_impact_pooled_eur)
    )
  })
  do.call(rbind, rows)
}
