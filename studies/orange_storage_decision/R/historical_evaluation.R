# Source model, sampling, evaluation, simulation, shared_shape, shape_ensemble,
# inspection_removals, inspection_plan_value and historical_baseline first.

# Synthetic archived observations; all were available before calendar day zero.
simulate_historical_inspections <- function(n_history = 100L, seed = 20261113L) {
  assert_nonnegative_scalar(n_history, "n_history", integer = TRUE)
  assert_nonnegative_scalar(seed, "seed", integer = TRUE)
  if (n_history < 2L) stop("at least two historical lots are required", call. = FALSE)
  set.seed(seed)
  do.call(rbind, lapply(seq_len(n_history), function(id) {
    truth <- simulate_true_inventory()
    rows <- expand.grid(cohort = truth$cohort[truth$initially_sellable],
      day = c(4L, 8L, 12L, 16L, 20L, 24L), stringsAsFactors = FALSE)
    index <- match(rows$cohort, truth$cohort)
    p <- weibull_survival(rows$day, truth$shape[index], truth$scale[index])
    rows$n_checked <- 60L
    rows$n_acceptable <- stats::rbinom(nrow(rows), 60L, inspection_label_probability(p, 0.9, 0.9))
    rows$lot_id <- sprintf("history-%03d", id)
    rows$harvest_day <- -24L - id
    rows
  }))
}

historical_study_inventory <- function() {
  data.frame(cohort = c("advanced", "intermediate", "initially_immature"),
    mass_kg = c(350, 500, 150), initially_sellable = c(TRUE, TRUE, FALSE), shape = 1, scale = 1)
}

# Score full, uninspected finite populations after the historical decision is fixed.
historical_forecast_records <- function(lot_id, fitted, lifetimes) {
  do.call(rbind, lapply(c(16L, 20L, 24L), function(day) {
    eligible <- fitted[fitted$initially_sellable, ]
    counts <- data.frame(cohort = eligible$cohort, day = day,
      n_checked = lengths(lifetimes[eligible$cohort]),
      n_acceptable = vapply(lifetimes[eligible$cohort], function(times) sum(times > day), integer(1)))
    probability <- weibull_survival(rep(day, nrow(eligible)), eligible$shape, eligible$scale)
    score <- score_future_probabilities(counts, fitted, probability, 12L)
    data.frame(lot_id = lot_id, day = day,
      predicted_kg = sum(eligible$mass_kg * probability),
      accepted_kg = sum(eligible$mass_kg * counts$n_acceptable / counts$n_checked),
      brier = score$brier, log_loss = score$log_loss)
  }))
}

#' Evaluate one frozen historical model on independent target lots.
#' @param n_lots Target lots, at least two, never used for fitting or tuning.
#' @param n_history Historical lots used once to fit the frozen model.
#' @param history_seed Seed for the independent historical archive.
#' @param metadata_seed Seed for target lot parameters and prices.
#' @param fruit_seed Seed for paired target fruit outcomes.
#' @param sampling_seed Seed for target inspection samples and labels.
#' @return Archive, fitted model, paired returns and future forecast measurements.
run_historical_experiment <- function(n_lots = 200L, n_history = 100L, history_seed = 20261113L,
                                      metadata_seed = 20261114L, fruit_seed = 20261115L,
                                      sampling_seed = 20261116L) {
  for (field in c("n_lots", "metadata_seed", "fruit_seed", "sampling_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (n_lots < 2L) stop("at least two target lots are required", call. = FALSE)
  history <- simulate_historical_inspections(n_history, history_seed)
  model <- fit_historical_survival(history, historical_study_inventory(), 0L, 0.9, 0.9)
  # Freeze the model before generating any target lot. Target survival parameters
  # and inspection counts are never passed to this policy.
  set.seed(metadata_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    truth <- simulate_true_inventory()
    truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
    truth$mass_kg[2] <- 850 - truth$mass_kg[1]
    prices <- simulate_price_scenario(12L, 28L)
    lot_id <- sprintf("target-%03d", id)
    inventory <- transform(truth, shape = 1, scale = 1)
    day <- historical_sale_decision(model, lot_id, inventory, prices, 0L)$sale_day
    fitted <- historical_fitted_inventory(model, lot_id, inventory, 0L, 12L)
    list(lot_id = lot_id, truth = truth, prices = prices, fitted = fitted, historical_day = day)
  })
  # All historical dates are fixed before any target fruit outcomes are generated.
  set.seed(fruit_seed)
  for (id in seq_along(lots)) lots[[id]]$lifetimes <- simulate_fruit_lifetimes(lots[[id]]$truth)
  set.seed(sampling_seed)
  forecasts <- vector("list", n_lots)
  records <- lapply(seq_along(lots), function(id) {
    tryCatch({
      lot <- lots[[id]]
      roster <- plan_value_roster(lot$lifetimes)
      inventory <- transform(lot$truth, shape = 1, scale = 1)
      plans <- lapply(c(30L, 180L), function(budget) plan_value_observations(roster, budget))
      policies <- lapply(plans, function(plan) {
        fit_plan_value_policy(plan$inspections, inventory, lot$prices, plan$removals)
      })
      evaluate <- function(day) realised_sale_value(day, lot$truth, lot$prices, lot$lifetimes, 0.001, 0L, 2L)
      row <- data.frame(lot_id = lot$lot_id, sale_day_historical = lot$historical_day,
        return_historical_eur = evaluate(lot$historical_day),
        return_day12_eur = evaluate(12L), return_day16_eur = evaluate(16L))
      for (i in seq_along(plans)) {
        score <- score_plan_value(lot, plans[[i]], policies[[i]])
        name <- paste0("inspection_", c(30L, 180L)[i])
        row[[paste0("sale_day_", name)]] <- score$sale_day
        row[[paste0("return_", name, "_eur")]] <- score$return_before_labour_eur - 0.02 * score$inspection_count
      }
      forecasts[[id]] <<- historical_forecast_records(lot$lot_id, lot$fitted, lot$lifetimes)
      row
    }, error = function(error) {
      stop(sprintf("historical-policy target lot %d: %s", id, conditionMessage(error)), call. = FALSE)
    })
  })
  list(history = history, model = model, records = do.call(rbind, records), forecasts = do.call(rbind, forecasts))
}

validate_historical_records <- function(records, numeric_fields, paired_days = FALSE) {
  if (!is.data.frame(records) || !all(c("lot_id", numeric_fields) %in% names(records)) ||
      !is.character(records$lot_id) || anyNA(records$lot_id) || any(!nzchar(trimws(records$lot_id))) ||
      length(unique(records$lot_id)) < 2L ||
      any(!vapply(records[numeric_fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1)))) {
    stop("historical evaluation needs finite measurements from at least two identified target lots", call. = FALSE)
  }
  if (paired_days) {
    if (!setequal(records$day, c(16L, 20L, 24L)) || any(table(records$lot_id, records$day) != 1L)) {
      stop("forecasts must cover each target lot and declared future day exactly once", call. = FALSE)
    }
  } else if (anyDuplicated(records$lot_id)) {
    stop("return records must contain each target lot exactly once", call. = FALSE)
  }
  invisible(TRUE)
}

#' Paired target-lot intervals conditional on one fixed historical training archive.
summarize_historical_returns <- function(records, n_boot = 1000L) {
  comparators <- c("day12", "day16", "inspection_30", "inspection_180")
  fields <- c("sale_day_historical", "return_historical_eur", paste0("return_", comparators, "_eur"))
  validate_historical_records(records, fields)
  records <- records[order(records$lot_id), ]
  do.call(rbind, lapply(comparators, function(comparator) {
    other <- records[[paste0("return_", comparator, "_eur")]]
    difference <- records$return_historical_eur - other
    interval <- paired_lot_interval(difference, n_boot)
    data.frame(comparator = comparator, n_lots = nrow(records),
      mean_historical_sale_day = mean(records$sale_day_historical),
      mean_historical_return_eur = mean(records$return_historical_eur), mean_comparator_return_eur = mean(other),
      gain_mean_eur = unname(interval["mean"]), gain_lower_95_eur = unname(interval["lower_95"]),
      gain_upper_95_eur = unname(interval["upper_95"]), below_comparator_fraction = mean(difference < 0))
  }))
}

#' Inventory-level forecast bias and proper scores on future target fruit outcomes.
summarize_historical_forecasts <- function(forecasts, n_boot = 1000L) {
  validate_historical_records(forecasts, c("day", "predicted_kg", "accepted_kg", "brier", "log_loss"), TRUE)
  do.call(rbind, lapply(c(16L, 20L, 24L), function(day) {
    part <- forecasts[forecasts$day == day, ]
    part <- part[order(part$lot_id), ]
    interval <- paired_lot_interval(part$predicted_kg - part$accepted_kg, n_boot)
    data.frame(day = day, n_lots = nrow(part), mean_predicted_kg = mean(part$predicted_kg),
      mean_accepted_kg = mean(part$accepted_kg), mean_brier = mean(part$brier), mean_log_loss = mean(part$log_loss),
      bias_mean_kg = unname(interval["mean"]), bias_lower_95_kg = unname(interval["lower_95"]),
      bias_upper_95_kg = unname(interval["upper_95"]))
  }))
}
