# Source model, sampling, evaluation, simulation, robust_policy,
# historical_baseline, historical_evaluation, archive_uncertainty and
# historical_shift first. Base R only.

#' Choose a date minimising worst fitted regret over declared lifetime factors.
#' @param cohorts Fitted inventory; the rule never receives target true parameters.
#' @param prices Supplied known price grid, shared across all survival scenarios.
#' @param multipliers Distinct positive factors applied to eligible Weibull scales.
#' @param storage_eur_per_kg_day Nonnegative cost per initial eligible kg/day.
#' @param decision_day Whole cutoff, included among available sale dates.
#' @param delivery_lag_days Whole delay until quality assessment.
#' @return Decision, all-date regret grid and scenario-specific fitted values.
minimax_survival_regret_sale <- function(cohorts, prices, multipliers = c(0.75, 1, 1.25),
                                        storage_eur_per_kg_day = 0.001, decision_day = 12L,
                                        delivery_lag_days = 2L) {
  validate_cohorts(cohorts)
  if (!is.numeric(multipliers) || !length(multipliers) || any(!is.finite(multipliers)) ||
      any(multipliers <= 0) || anyDuplicated(multipliers)) {
    stop("decision multipliers must be distinct finite positive numbers", call. = FALSE)
  }
  multipliers <- sort(multipliers)
  grids <- lapply(multipliers, function(multiplier) {
    scenario <- cohorts
    scenario$scale[scenario$initially_sellable] <- scenario$scale[scenario$initially_sellable] * multiplier
    expected_value_grid(scenario, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days)
  })
  if (!decision_day %in% grids[[1]]$sale_day) stop("prices must include the decision day", call. = FALSE)
  names(grids) <- paste0("lifetime_", seq_along(multipliers))
  result <- minimax_regret_grids(grids)
  result$scenario_values$lifetime_multiplier <- multipliers[match(result$scenario_values$scenario, names(grids))]
  result
}

#' Apply survival minimax regret with the historical model's ID/calendar checks.
historical_minimax_sale <- function(model, lot_id, inventory, prices, harvest_day,
                                    multipliers = c(0.75, 1, 1.25), decision_day = 12L,
                                    storage_eur_per_kg_day = 0.001, delivery_lag_days = 2L) {
  fitted <- historical_fitted_inventory(model, lot_id, inventory, harvest_day, decision_day)
  minimax_survival_regret_sale(fitted, prices, multipliers, storage_eur_per_kg_day, decision_day, delivery_lag_days)
}

run_survival_regret_replication <- function(repetition, n_targets, n_history, decision_multipliers,
                                           evaluation_multipliers, history_seed, metadata_seed, fruit_seed) {
  for (field in c("repetition", "n_targets", "n_history", "history_seed", "metadata_seed", "fruit_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (repetition < 1L || n_targets < 2L || n_history < 2L) stop("need a positive repetition and at least two historical/target lots", call. = FALSE)
  validate_lifetime_multipliers(evaluation_multipliers)
  history <- simulate_historical_inspections(n_history, history_seed)
  history$lot_id <- sprintf("regret-%03d-%s", repetition, history$lot_id)
  model <- fit_historical_survival(history, historical_study_inventory(), 0L, 0.9, 0.9)
  set.seed(metadata_seed)
  targets <- lapply(seq_len(n_targets), function(id) {
    truth <- simulate_true_inventory()
    truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
    truth$mass_kg[2] <- 850 - truth$mass_kg[1]
    prices <- simulate_price_scenario(12L, 28L)
    lot_id <- sprintf("regret-%03d-target-%03d", repetition, id)
    inventory <- transform(truth, shape = 1, scale = 1)
    nominal <- historical_sale_decision(model, lot_id, inventory, prices, 0L)$sale_day
    robust <- historical_minimax_sale(model, lot_id, inventory, prices, 0L, decision_multipliers)
    list(lot_id = lot_id, truth = truth, prices = prices, nominal_day = nominal,
      robust_day = robust$decision$sale_day, robust_regret = robust$decision$worst_regret_eur,
      nominal_regret = robust$grid$worst_regret_eur[robust$grid$sale_day == nominal])
  })
  # All nominal and robust dates are fixed before any target outcomes exist.
  set.seed(fruit_seed)
  records <- lapply(targets, function(lot) {
    times <- simulate_fruit_lifetimes(lot$truth)
    do.call(rbind, lapply(evaluation_multipliers, function(multiplier) {
      shifted <- scale_fruit_lifetimes(times, multiplier)
      evaluate <- function(day) realised_sale_value(day, lot$truth, lot$prices, shifted, 0.001, 0L, 2L)
      nominal <- evaluate(lot$nominal_day)
      robust <- evaluate(lot$robust_day)
      day12 <- evaluate(12L)
      data.frame(repetition = repetition, lot_id = lot$lot_id, lifetime_multiplier = multiplier,
        nominal_day = lot$nominal_day, robust_day = lot$robust_day,
        fitted_nominal_worst_regret_eur = lot$nominal_regret, fitted_robust_worst_regret_eur = lot$robust_regret,
        nominal_return_eur = nominal, robust_return_eur = robust, day12_return_eur = day12,
        robust_minus_nominal_eur = robust - nominal, nominal_minus_day12_eur = nominal - day12,
        robust_minus_day12_eur = robust - day12, robust_below_nominal = as.integer(robust < nominal),
        nominal_below_day12 = as.integer(nominal < day12), robust_below_day12 = as.integer(robust < day12))
    }))
  })
  list(records = do.call(rbind, records), counts = data.frame(repetition = repetition, model$counts),
    fits = data.frame(repetition = repetition, model$fits))
}

#' Compare fixed historical and survival-regret policies on fresh paired shifts.
#' @return Records, aggregate training counts, fitted curves and stream seeds.
run_survival_regret_experiment <- function(n_repeats = 30L, n_targets = 50L, n_history = 100L,
                                           decision_multipliers = c(0.75, 1, 1.25),
                                           evaluation_multipliers = c(0.6, 0.75, 1, 1.25, 1.4),
                                           master_seed = 20261119L) {
  seeds <- archive_seed_manifest(n_repeats, master_seed)
  runs <- lapply(seq_len(n_repeats), function(i) {
    tryCatch(run_survival_regret_replication(i, n_targets, n_history, decision_multipliers, evaluation_multipliers,
      seeds$history_seed[i], seeds$metadata_seed[i], seeds$fruit_seed[i]), error = function(error) {
        stop(sprintf("survival-regret repetition %d: %s", i, conditionMessage(error)), call. = FALSE)
      })
  })
  collect <- function(field) do.call(rbind, lapply(runs, `[[`, field))
  list(records = collect("records"), counts = collect("counts"), fits = collect("fits"), seeds = seeds)
}

survival_regret_metrics <- function() c("robust_minus_nominal_eur", "nominal_minus_day12_eur",
  "robust_minus_day12_eur", "robust_below_nominal", "nominal_below_day12", "robust_below_day12")

survival_regret_repetition_means <- function(records) {
  fixed <- c("nominal_day", "robust_day", "fitted_nominal_worst_regret_eur", "fitted_robust_worst_regret_eur")
  metrics <- c(fixed, "nominal_return_eur", "robust_return_eur", "day12_return_eur", survival_regret_metrics())
  fields <- c("repetition", "lifetime_multiplier", metrics)
  if (!is.data.frame(records) || !all(c("lot_id", fields) %in% names(records)) ||
      !is.character(records$lot_id) || anyNA(records$lot_id) || any(!nzchar(trimws(records$lot_id))) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1)))) {
    stop("need identified target/scenario records with finite numeric measurements", call. = FALSE)
  }
  factors <- sort(unique(records$lifetime_multiplier))
  validate_lifetime_multipliers(factors)
  if (length(unique(records$repetition)) < 2L || any(records$repetition < 1 | records$repetition != floor(records$repetition)) ||
      anyDuplicated(records[c("repetition", "lot_id", "lifetime_multiplier")])) {
    stop("need at least two repetitions and unique target/scenario records", call. = FALSE)
  }
  panels <- split(records, records$repetition)
  counts <- vapply(panels, function(x) length(unique(x$lot_id)), integer(1))
  if (any(counts < 2L) || length(unique(counts)) != 1L || length(unique(records$lot_id)) != sum(counts)) {
    stop("target panels must be equally sized and disjoint, with at least two lots", call. = FALSE)
  }
  for (part in panels) {
    if (!setequal(part$lifetime_multiplier, factors) || any(table(part$lot_id, part$lifetime_multiplier) != 1L)) {
      stop("every target must appear once per evaluation scenario", call. = FALSE)
    }
    for (lot in split(part, part$lot_id)) {
      if (any(vapply(lot[fixed], function(x) length(unique(x)) != 1L, logical(1)))) {
        stop("dates and fitted regrets must be fixed before evaluation scenarios", call. = FALSE)
      }
    }
  }
  contrasts <- list(robust_minus_nominal_eur = records$robust_return_eur - records$nominal_return_eur,
    nominal_minus_day12_eur = records$nominal_return_eur - records$day12_return_eur,
    robust_minus_day12_eur = records$robust_return_eur - records$day12_return_eur)
  for (field in names(contrasts)) {
    if (any(abs(records[[field]] - contrasts[[field]]) > 1e-8)) stop("return contrasts do not match paired outcomes", call. = FALSE)
  }
  if (any(records$robust_below_nominal != as.integer(contrasts$robust_minus_nominal_eur < 0)) ||
      any(records$nominal_below_day12 != as.integer(contrasts$nominal_minus_day12_eur < 0)) ||
      any(records$robust_below_day12 != as.integer(contrasts$robust_minus_day12_eur < 0)) ||
      any(records$fitted_robust_worst_regret_eur > records$fitted_nominal_worst_regret_eur + 1e-8)) {
    stop("downside indicators or fitted minimax inequalities are inconsistent", call. = FALSE)
  }
  records <- records[order(records$repetition, records$lifetime_multiplier, records$lot_id), ]
  blocks <- stats::aggregate(records[metrics], records[c("repetition", "lifetime_multiplier")], mean)
  blocks$n_targets <- unname(counts[as.character(blocks$repetition)])
  blocks <- blocks[order(blocks$repetition, blocks$lifetime_multiplier), ]
  rownames(blocks) <- NULL
  blocks
}

#' Paired whole-repetition intervals, conditional on each declared target shift.
summarize_survival_regret <- function(records, n_boot = 2000L) {
  blocks <- survival_regret_repetition_means(records)
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  if (n_boot < 1L) stop("n_boot must be positive", call. = FALSE)
  n_repeats <- length(unique(blocks$repetition))
  draws <- matrix(sample.int(n_repeats, n_repeats * n_boot, replace = TRUE), nrow = n_repeats)
  summary <- do.call(rbind, lapply(sort(unique(blocks$lifetime_multiplier)), function(factor) {
    part <- blocks[blocks$lifetime_multiplier == factor, ]
    do.call(rbind, lapply(survival_regret_metrics(), function(metric) {
      values <- part[[metric]]
      means <- colMeans(matrix(values[draws], nrow = n_repeats))
      bounds <- stats::quantile(means, c(0.025, 0.975), names = FALSE)
      data.frame(lifetime_multiplier = factor, metric = metric, n_repeats = n_repeats,
        mean = mean(values), lower_95 = bounds[1], upper_95 = bounds[2])
    }))
  }))
  list(repetitions = blocks, summary = summary)
}
