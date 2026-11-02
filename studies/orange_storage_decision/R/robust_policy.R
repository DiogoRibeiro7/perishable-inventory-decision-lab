# Finite-scenario minimax regret. Source model.R first; price_mean_scenarios()
# additionally needs price_sensitivity.R.

# Shared criterion for expected-value grids from price or survival scenarios.
minimax_regret_grids <- function(grids) {
  labels <- names(grids)
  if (!is.list(grids) || is.data.frame(grids) || !length(grids) || is.null(labels) ||
      anyNA(labels) || any(!nzchar(trimws(labels))) || anyDuplicated(labels) ||
      any(!vapply(grids, function(x) {
        is.data.frame(x) && nrow(x) > 0L && all(c("sale_day", "expected_net_eur") %in% names(x)) &&
          is.numeric(x$sale_day) && all(is.finite(x$sale_day)) && all(x$sale_day >= 0) &&
          all(x$sale_day == floor(x$sale_day)) && !anyDuplicated(x$sale_day) &&
          is.numeric(x$expected_net_eur) && all(is.finite(x$expected_net_eur))
      }, logical(1)))) {
    stop("grids need unique scenario names, distinct whole sale days and finite expected values", call. = FALSE)
  }
  grids <- lapply(grids, function(x) x[order(x$sale_day), ])
  days <- grids[[1]]$sale_day
  if (any(!vapply(grids, function(x) length(x$sale_day) == length(days) && all(x$sale_day == days), logical(1)))) {
    stop("scenario grids must share candidate sale days", call. = FALSE)
  }
  values <- vapply(grids, function(x) x$expected_net_eur, numeric(length(days)))
  # Keep matrix dimensions for a single date or a single scenario.
  values <- matrix(values, nrow = length(days), ncol = length(grids))
  regrets <- sweep(-values, 2, apply(values, 2, max), "+")
  grid <- data.frame(sale_day = days, worst_regret_eur = apply(regrets, 1, max),
    worst_expected_net_eur = apply(values, 1, min), best_expected_net_eur = apply(values, 1, max))
  details <- do.call(rbind, lapply(seq_along(grids), function(i) {
    data.frame(scenario = labels[i], sale_day = days, expected_net_eur = values[, i], regret_eur = regrets[, i])
  }))
  list(decision = grid[which.min(grid$worst_regret_eur), , drop = FALSE],
    grid = grid, scenario_values = details)
}

#' Construct deterministic conditional-mean price paths for a decision rule.
#' @param prices Forecast price grid, starting at decision_day.
#' @param cohorts Fitted inventory; used only for validating price coverage.
#' @param decision_day First sale day, with its price known exactly.
#' @param terminal_mean_multipliers Positive distinct terminal mean ratios.
#' @return Named list of complete mean price grids; consumes no random numbers.
price_mean_scenarios <- function(prices, cohorts, decision_day,
                                 terminal_mean_multipliers = c(0.6, 0.8, 1)) {
  ratios <- terminal_mean_multipliers
  if (!is.numeric(ratios) || length(ratios) < 1L || anyNA(ratios) ||
      any(!is.finite(ratios)) || any(ratios <= 0) || anyDuplicated(ratios)) {
    stop("terminal mean ratios must be distinct finite positive numbers",
         call. = FALSE)
  }
  paths <- lapply(ratios, function(ratio) {
    apply_price_error(prices, cohorts, decision_day, ratio, terminal_log_sd = 0)
  })
  names(paths) <- paste0("mean_ratio_", seq_along(ratios))
  paths
}

#' Choose the earliest date minimising worst expected regret across scenarios.
#'
#' Regret at day d in scenario s is max_t V_s(t) - V_s(d), where V is fitted
#' expected net return. This is a finite-set decision criterion, not a bound
#' on realised losses, and no scenario probabilities are required.
#'
#' @param cohorts Inventory with survival parameters fitted before the cutoff.
#' @param price_scenarios Nonempty uniquely named list of complete price grids.
#'   Each grid must offer the same future days and the same known current quote.
#' @param storage_eur_per_kg_day Per-initial-kg daily holding cost.
#' @param decision_day Information cutoff, included among the candidate dates.
#' @param delivery_lag_days Delay until commercial acceptance.
#' @return List: decision (one row), grid (all dates), and scenario_values
#'   (expected values and regrets for every scenario/date).
minimax_regret_sale <- function(cohorts, price_scenarios,
                                storage_eur_per_kg_day, decision_day,
                                delivery_lag_days = 0) {
  labels <- names(price_scenarios)
  if (!is.list(price_scenarios) || is.data.frame(price_scenarios) ||
      length(price_scenarios) < 1L || is.null(labels) || anyNA(labels) ||
      any(!nzchar(trimws(labels))) || anyDuplicated(labels)) {
    stop("price_scenarios must be a uniquely named nonempty list", call. = FALSE)
  }
  grids <- lapply(price_scenarios, function(prices) {
    expected_value_grid(cohorts, prices, storage_eur_per_kg_day,
                         decision_day, delivery_lag_days)
  })
  days <- grids[[1]]$sale_day
  if (!(decision_day %in% days) ||
      any(!vapply(grids, function(x) {
        length(x$sale_day) == length(days) && all(x$sale_day == days)
      }, logical(1)))) {
    stop("scenarios must share candidate days including decision_day", call. = FALSE)
  }
  current_quote <- function(prices) {
    part <- prices[prices$day == decision_day, ]
    part$price_eur_per_kg[order(part$cohort)]
  }
  known <- current_quote(price_scenarios[[1]])
  if (any(!vapply(price_scenarios, function(x) {
    all(current_quote(x) == known)
  }, logical(1)))) {
    stop("scenarios must share the known decision-day quote", call. = FALSE)
  }
  minimax_regret_grids(grids)
}
