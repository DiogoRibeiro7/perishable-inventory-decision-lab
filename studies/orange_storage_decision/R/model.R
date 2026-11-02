#' Heterogeneous postharvest survival and selling decisions.
#'
#' All monetary values are euros. Masses are kilograms. Time is measured in
#' whole days since harvest. The model intentionally uses base R only.

#' Check a finite scalar used as a nonnegative model input.
#' @param value Numeric scalar.
#' @param name Name used in error messages.
#' @param integer Whether only whole numbers are allowed.
assert_nonnegative_scalar <- function(value, name, integer = FALSE) {
  if (!is.numeric(value) || length(value) != 1L || is.na(value) ||
      !is.finite(value) || value < 0 || (integer && value != floor(value))) {
    stop(sprintf("%s must be a finite nonnegative%s scalar",
                 name, if (integer) " integer" else ""), call. = FALSE)
  }
  invisible(TRUE)
}

#' Validate the stratified inventory at harvest.
#' @param cohorts Data frame with cohort, mass_kg, initially_sellable, shape,
#'   and scale columns. Shape and scale describe Weibull survival after harvest.
validate_cohorts <- function(cohorts) {
  required <- c("cohort", "mass_kg", "initially_sellable", "shape", "scale")
  if (!is.data.frame(cohorts) || !all(required %in% names(cohorts)) ||
      nrow(cohorts) < 1L) {
    stop("cohorts must be a nonempty data frame with required columns",
         call. = FALSE)
  }
  if (!is.character(cohorts$cohort) || anyNA(cohorts$cohort) ||
      any(!nzchar(trimws(cohorts$cohort))) || anyDuplicated(cohorts$cohort)) {
    stop("cohort labels must be nonempty and unique", call. = FALSE)
  }
  if (!is.logical(cohorts$initially_sellable) ||
      anyNA(cohorts$initially_sellable)) {
    stop("initially_sellable must contain nonmissing logical values",
         call. = FALSE)
  }
  for (column in c("mass_kg", "shape", "scale")) {
    values <- cohorts[[column]]
    if (!is.numeric(values) || anyNA(values) ||
        any(!is.finite(values)) || any(values <= 0)) {
      stop(sprintf("%s must contain finite positive numbers", column),
           call. = FALSE)
    }
  }
  if (!any(cohorts$initially_sellable)) {
    stop("at least one cohort must qualify for fresh-market sale",
         call. = FALSE)
  }
  invisible(TRUE)
}

#' Weibull probability of remaining commercially acceptable.
#' @param days Nonnegative storage duration(s).
#' @param shape Positive Weibull shape(s), scalar or same length as days.
#' @param scale Positive Weibull scale(s), scalar or same length as days.
#' @return Numeric probabilities in [0, 1].
weibull_survival <- function(days, shape, scale) {
  if (!is.numeric(days) || length(days) < 1L || anyNA(days) ||
      any(!is.finite(days)) || any(days < 0)) {
    stop("days must contain finite nonnegative values", call. = FALSE)
  }
  for (parameter in list(shape = shape, scale = scale)) {
    if (!is.numeric(parameter) || anyNA(parameter) ||
        any(!is.finite(parameter)) || any(parameter <= 0) ||
        !(length(parameter) %in% c(1L, length(days)))) {
      stop("shape and scale must be positive and have compatible lengths",
           call. = FALSE)
    }
  }
  exp(-((days / scale) ^ shape))
}

#' Validate future price scenarios against the initially saleable cohorts.
#' @param prices Data frame: cohort, day, price_eur_per_kg.
#' @param cohorts Validated inventory data frame.
validate_prices <- function(prices, cohorts) {
  required <- c("cohort", "day", "price_eur_per_kg")
  if (!is.data.frame(prices) || !all(required %in% names(prices)) ||
      nrow(prices) < 1L || !is.character(prices$cohort) ||
      anyNA(prices$cohort) || !is.numeric(prices$day) ||
      anyNA(prices$day) || any(!is.finite(prices$day)) ||
      any(prices$day < 0 | prices$day != floor(prices$day)) ||
      !is.numeric(prices$price_eur_per_kg) ||
      anyNA(prices$price_eur_per_kg) ||
      any(!is.finite(prices$price_eur_per_kg)) ||
      any(prices$price_eur_per_kg < 0)) {
    stop("prices must have valid cohort, whole-day and nonnegative price fields",
         call. = FALSE)
  }
  if (anyDuplicated(prices[c("cohort", "day")])) {
    stop("each cohort/day price must occur exactly once", call. = FALSE)
  }
  eligible <- cohorts$cohort[cohorts$initially_sellable]
  if (!setequal(unique(prices$cohort), eligible)) {
    stop("prices must cover exactly the initially saleable cohorts",
         call. = FALSE)
  }
  days <- sort(unique(prices$day))
  for (group in eligible) {
    if (!setequal(prices$day[prices$cohort == group], days)) {
      stop("every saleable cohort needs a price for every candidate day",
           call. = FALSE)
    }
  }
  invisible(TRUE)
}

#' Expected whole-batch revenue for every possible selling day.
#'
#' The price is agreed on the sale day; freshness is assessed upon delivery.
#' Storage cost is charged per initial saleable kilogram for each additional
#' day, even if part of that cohort deteriorates in the meantime. Initially
#' unsellable oranges are excluded and must be separately triaged.
#'
#' @param cohorts Inventory with calibrated Weibull parameters.
#' @param prices Expected prices, one row per cohort and candidate day.
#' @param storage_eur_per_kg_day Marginal holding cost per initial kilogram/day.
#' @param decision_day Earliest allowed selling day (information cut-off).
#' @param delivery_lag_days Whole days between sale and quality assessment.
#' @return Data frame sorted by sale_day with expected net value.
expected_value_grid <- function(cohorts, prices, storage_eur_per_kg_day,
                                decision_day = 0, delivery_lag_days = 0) {
  validate_cohorts(cohorts)
  validate_prices(prices, cohorts)
  assert_nonnegative_scalar(storage_eur_per_kg_day,
                            "storage_eur_per_kg_day")
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  assert_nonnegative_scalar(delivery_lag_days, "delivery_lag_days",
                            integer = TRUE)

  eligible <- cohorts[cohorts$initially_sellable, , drop = FALSE]
  days <- sort(unique(prices$day[prices$day >= decision_day]))
  if (length(days) == 0L) {
    stop("no candidate selling day on or after decision_day", call. = FALSE)
  }

  rows <- lapply(days, function(day) {
    quote <- prices[prices$day == day, , drop = FALSE]
    quote <- quote[match(eligible$cohort, quote$cohort), , drop = FALSE]
    delivery_day <- day + delivery_lag_days
    probability <- weibull_survival(rep(delivery_day, nrow(eligible)),
                                    eligible$shape, eligible$scale)
    expected_mass <- sum(eligible$mass_kg * probability)
    gross <- sum(eligible$mass_kg * probability * quote$price_eur_per_kg)
    cost <- sum(eligible$mass_kg) * storage_eur_per_kg_day *
      (day - decision_day + delivery_lag_days)
    data.frame(sale_day = day, delivery_day = delivery_day,
               expected_sellable_kg = expected_mass,
               expected_gross_eur = gross,
               additional_storage_eur = cost,
               expected_net_eur = gross - cost)
  })
  do.call(rbind, rows)
}

#' Earliest expected-value-maximising whole-batch selling day.
#' @param ... Arguments forwarded to expected_value_grid().
#' @return One-row data frame.
optimal_batch_sale <- function(...) {
  grid <- expected_value_grid(...)
  grid[which.max(grid$expected_net_eur), , drop = FALSE]
}

#' Optimise a separate selling day for each saleable cohort.
#'
#' This policy assumes groups are physically separable and that splitting
#' introduces no additional transaction costs or shared capacity constraints.
#' @param cohorts Inventory with calibrated Weibull parameters.
#' @param prices Expected cohort-specific prices by selling day.
#' @param storage_eur_per_kg_day Per-kg daily holding cost.
#' @param decision_day Earliest allowed selling day.
#' @param delivery_lag_days Delay until quality assessment.
#' @return One row per saleable cohort with its optimal day and value.
optimal_split_sales <- function(cohorts, prices, storage_eur_per_kg_day,
                                decision_day = 0, delivery_lag_days = 0) {
  validate_cohorts(cohorts)
  validate_prices(prices, cohorts)
  groups <- cohorts$cohort[cohorts$initially_sellable]
  rows <- lapply(groups, function(group) {
    single <- optimal_batch_sale(
      cohorts[cohorts$cohort == group, , drop = FALSE],
      prices[prices$cohort == group, , drop = FALSE],
      storage_eur_per_kg_day, decision_day, delivery_lag_days
    )
    data.frame(cohort = group, single, row.names = NULL)
  })
  do.call(rbind, rows)
}
