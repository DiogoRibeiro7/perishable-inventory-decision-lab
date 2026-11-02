# Source model, sampling, evaluation, simulation, historical_baseline,
# historical_evaluation and archive_uncertainty first. Base R only.

validate_lifetime_multipliers <- function(multipliers) {
  if (!is.numeric(multipliers) || length(multipliers) < 2L || any(!is.finite(multipliers)) ||
      any(multipliers <= 0) || anyDuplicated(multipliers) || !1 %in% multipliers) {
    stop("need unique positive lifetime multipliers including the unchanged value 1", call. = FALSE)
  }
  invisible(TRUE)
}

#' Couple a shelf-life shift from harvest by multiplying every fruit lifetime.
#' For Weibull fruit this multiplies scale, leaves shape unchanged and preserves
#' fruit identity. This is not a constant hazard multiplier across strata.
scale_fruit_lifetimes <- function(lifetimes, multiplier) {
  assert_nonnegative_scalar(multiplier, "multiplier")
  if (multiplier == 0 || !is.list(lifetimes) || !length(lifetimes) ||
      is.null(names(lifetimes)) || anyNA(names(lifetimes)) || any(!nzchar(names(lifetimes))) ||
      anyDuplicated(names(lifetimes)) ||
      any(!vapply(lifetimes, function(x) is.numeric(x) && length(x) > 0L &&
        all(is.finite(x)) && all(x >= 0), logical(1)))) {
    stop("need named finite nonnegative fruit lifetimes and a positive multiplier", call. = FALSE)
  }
  result <- lapply(lifetimes, function(times) times * multiplier)
  if (any(!is.finite(unlist(result)))) stop("scaled lifetimes overflowed", call. = FALSE)
  result
}

score_historical_shift <- function(lot, lifetimes, multiplier, repetition) {
  shifted <- scale_fruit_lifetimes(lifetimes, multiplier)
  evaluate <- function(day) realised_sale_value(day, lot$truth, lot$prices, shifted, 0.001, 0L, 2L)
  value <- evaluate(lot$sale_day)
  day12 <- evaluate(12L)
  day16 <- evaluate(16L)
  forecasts <- historical_forecast_records(lot$lot_id, lot$fitted, shifted)
  row <- data.frame(repetition = repetition, lot_id = lot$lot_id, lifetime_multiplier = multiplier,
    sale_day = lot$sale_day, return_eur = value, return_day12_eur = day12, return_day16_eur = day16,
    gain_day12_eur = value - day12, gain_day16_eur = value - day16,
    below_day12 = as.integer(value < day12), brier = mean(forecasts$brier), log_loss = mean(forecasts$log_loss))
  for (day in c(16L, 20L, 24L)) {
    x <- forecasts[forecasts$day == day, ]
    row[[paste0("predicted_day", day, "_kg")]] <- x$predicted_kg
    row[[paste0("accepted_day", day, "_kg")]] <- x$accepted_kg
    row[[paste0("bias_day", day, "_kg")]] <- x$predicted_kg - x$accepted_kg
  }
  row
}

# One archive and target panel; shift scenarios are potential outcomes for the
# same fruit, with the same masses, prices, forecasts and fixed sale decisions.
run_historical_shift_replication <- function(repetition, n_targets, n_history,
                                             multipliers, history_seed, metadata_seed, fruit_seed) {
  for (field in c("repetition", "n_targets", "n_history", "history_seed", "metadata_seed", "fruit_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (repetition < 1L || n_targets < 2L || n_history < 2L) {
    stop("need a positive repetition ID and at least two historical/target lots", call. = FALSE)
  }
  validate_lifetime_multipliers(multipliers)
  history <- simulate_historical_inspections(n_history, history_seed)
  history$lot_id <- sprintf("shift-%03d-%s", repetition, history$lot_id)
  model <- fit_historical_survival(history, historical_study_inventory(), 0L, 0.9, 0.9)
  set.seed(metadata_seed)
  targets <- lapply(seq_len(n_targets), function(id) {
    truth <- simulate_true_inventory()
    truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
    truth$mass_kg[2] <- 850 - truth$mass_kg[1]
    prices <- simulate_price_scenario(12L, 28L)
    lot_id <- sprintf("shift-%03d-target-%03d", repetition, id)
    inventory <- transform(truth, shape = 1, scale = 1)
    sale_day <- historical_sale_decision(model, lot_id, inventory, prices, 0L)$sale_day
    fitted <- historical_fitted_inventory(model, lot_id, inventory, 0L, 12L)
    list(lot_id = lot_id, truth = truth, prices = prices, fitted = fitted, sale_day = sale_day)
  })
  # All decisions precede every target outcome; the policy never sees a shift.
  set.seed(fruit_seed)
  records <- lapply(targets, function(lot) {
    lifetimes <- simulate_fruit_lifetimes(lot$truth)
    do.call(rbind, lapply(multipliers, function(multiplier) {
      score_historical_shift(lot, lifetimes, multiplier, repetition)
    }))
  })
  list(records = do.call(rbind, records), counts = data.frame(repetition = repetition, model$counts),
    fits = data.frame(repetition = repetition, model$fits))
}

#' Evaluate a frozen historical policy under prespecified target shelf-life shifts.
#' @param n_repeats Independent training-archive/target-panel draws, at least two.
#' @param n_targets Fresh target lots per repetition, at least two.
#' @param n_history Completed historical lots fitted per repetition, at least two.
#' @param multipliers Positive lifetime factors including 1; shared by both strata.
#' @param master_seed Seed for distinct archive/metadata/fruit seeds per repetition.
#' @return Target/scenario measurements, training counts, fits and seed manifest.
run_historical_shift_experiment <- function(n_repeats = 30L, n_targets = 50L, n_history = 100L,
                                            multipliers = c(0.75, 1, 1.25), master_seed = 20261118L) {
  validate_lifetime_multipliers(multipliers)
  seeds <- archive_seed_manifest(n_repeats, master_seed)
  runs <- lapply(seq_len(n_repeats), function(i) {
    tryCatch(run_historical_shift_replication(i, n_targets, n_history, multipliers,
      seeds$history_seed[i], seeds$metadata_seed[i], seeds$fruit_seed[i]), error = function(error) {
        stop(sprintf("historical-shift repetition %d: %s", i, conditionMessage(error)), call. = FALSE)
      })
  })
  collect <- function(field) do.call(rbind, lapply(runs, `[[`, field))
  list(records = collect("records"), counts = collect("counts"), fits = collect("fits"), seeds = seeds)
}

historical_shift_metrics <- function() c("return_eur", "gain_day12_eur", "gain_day16_eur", "below_day12",
  "brier", "log_loss", "bias_day16_kg", "bias_day20_kg", "bias_day24_kg")

historical_shift_repetition_means <- function(records) {
  predicted <- paste0("predicted_day", c(16L, 20L, 24L), "_kg")
  accepted <- paste0("accepted_day", c(16L, 20L, 24L), "_kg")
  metrics <- c("sale_day", "return_day12_eur", "return_day16_eur", historical_shift_metrics(), predicted, accepted)
  fields <- c("repetition", "lifetime_multiplier", metrics)
  if (!is.data.frame(records) || !all(c("lot_id", fields) %in% names(records)) ||
      !is.character(records$lot_id) || anyNA(records$lot_id) || any(!nzchar(trimws(records$lot_id))) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1)))) {
    stop("shift records need identified targets and finite numeric measurements", call. = FALSE)
  }
  factors <- sort(unique(records$lifetime_multiplier))
  validate_lifetime_multipliers(factors)
  if (length(unique(records$repetition)) < 2L || any(records$repetition < 1) ||
      any(records$repetition != floor(records$repetition)) ||
      anyDuplicated(records[c("repetition", "lot_id", "lifetime_multiplier")])) {
    stop("need at least two repetitions and unique target/scenario records", call. = FALSE)
  }
  panels <- split(records, records$repetition)
  counts <- vapply(panels, function(part) length(unique(part$lot_id)), integer(1))
  if (any(counts < 2L) || length(unique(counts)) != 1L || length(unique(records$lot_id)) != sum(counts)) {
    stop("target panels must be equally sized, disjoint and contain at least two lots", call. = FALSE)
  }
  for (part in panels) {
    if (!setequal(part$lifetime_multiplier, factors) || any(table(part$lot_id, part$lifetime_multiplier) != 1L)) {
      stop("every target must appear exactly once in every shift scenario", call. = FALSE)
    }
    for (lot in split(part, part$lot_id)) {
      if (any(vapply(lot[c("sale_day", predicted)], function(x) length(unique(x)) != 1L, logical(1)))) {
        stop("sale dates and predicted masses must be fixed across shift scenarios", call. = FALSE)
      }
    }
  }
  if (any(abs(records$gain_day12_eur - (records$return_eur - records$return_day12_eur)) > 1e-8) ||
      any(abs(records$gain_day16_eur - (records$return_eur - records$return_day16_eur)) > 1e-8) ||
      any(records$below_day12 != as.integer(records$gain_day12_eur < 0))) {
    stop("return gains and downside indicators must match paired returns", call. = FALSE)
  }
  for (i in seq_along(predicted)) {
    bias <- records[[paste0("bias_day", c(16L, 20L, 24L)[i], "_kg")]]
    if (any(abs(bias - (records[[predicted[i]]] - records[[accepted[i]]])) > 1e-8)) {
      stop("bias must equal predicted minus observed acceptable mass", call. = FALSE)
    }
  }
  records <- records[order(records$repetition, records$lifetime_multiplier, records$lot_id), ]
  blocks <- stats::aggregate(records[metrics], records[c("repetition", "lifetime_multiplier")], mean)
  blocks$n_targets <- unname(counts[as.character(blocks$repetition)])
  blocks <- blocks[order(blocks$repetition, blocks$lifetime_multiplier), ]
  rownames(blocks) <- NULL
  blocks
}

#' Bootstrap independent train/test repetitions with all shift scenarios paired.
#' Intervals concern expected performance under each declared scenario, not the
#' probability of a shift occurring or the outcome of one deployed model/lot.
summarize_historical_shift <- function(records, n_boot = 2000L) {
  blocks <- historical_shift_repetition_means(records)
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  if (n_boot < 1L) stop("n_boot must be positive", call. = FALSE)
  factors <- sort(unique(blocks$lifetime_multiplier))
  baseline <- blocks[blocks$lifetime_multiplier == 1, ]
  n_repeats <- nrow(baseline)
  # Reuse the same repetition indices across all metrics and scenarios.
  draws <- matrix(sample.int(n_repeats, n_repeats * n_boot, replace = TRUE), nrow = n_repeats)
  interval <- function(values) {
    averages <- colMeans(matrix(values[draws], nrow = n_repeats))
    bounds <- stats::quantile(averages, c(0.025, 0.975), names = FALSE)
    data.frame(n_repeats = n_repeats, mean = mean(values), lower_95 = bounds[1], upper_95 = bounds[2])
  }
  collect <- function(contrast) do.call(rbind, lapply(if (contrast) factors[factors != 1] else factors, function(factor) {
    part <- blocks[blocks$lifetime_multiplier == factor, ]
    stopifnot(identical(part$repetition, baseline$repetition))
    do.call(rbind, lapply(historical_shift_metrics(), function(metric) {
      values <- part[[metric]]
      if (contrast) values <- values - baseline[[metric]]
      data.frame(lifetime_multiplier = factor, metric = metric, interval(values))
    }))
  }))
  list(repetitions = blocks, summary = collect(FALSE), contrasts = collect(TRUE))
}
