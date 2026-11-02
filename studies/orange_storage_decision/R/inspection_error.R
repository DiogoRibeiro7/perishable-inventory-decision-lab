# Source model, sampling, evaluation and simulation first.

default_inspection_scenarios <- function() {
  data.frame(scenario = c("perfect", "balanced_errors", "more_false_accepts",
                           "more_false_rejects"),
              sensitivity = c(1, 0.9, 0.95, 0.8), specificity = c(1, 0.9, 0.8, 0.95))
}

validate_inspection_scenarios <- function(scenarios) {
  if (!is.data.frame(scenarios) || nrow(scenarios) < 1L ||
      !all(c("scenario", "sensitivity", "specificity") %in% names(scenarios)) ||
      !is.character(scenarios$scenario) || anyNA(scenarios$scenario) ||
      any(!nzchar(trimws(scenarios$scenario))) || anyDuplicated(scenarios$scenario)) {
    stop("scenarios need unique names and sensitivity/specificity", call. = FALSE)
  }
  for (i in seq_len(nrow(scenarios))) {
    invisible(inspection_label_probability(0.5, scenarios$sensitivity[i],
                                            scenarios$specificity[i]))
  }
  invisible(TRUE)
}

#' Apply classification errors to shared true training counts.
#' @param clean Inspections containing the true acceptable counts.
#' @param inventory Initial inventory for count validation.
#' @param sensitivity Known probability of accepting truly acceptable fruit.
#' @param specificity Known probability of rejecting truly unacceptable fruit.
#' @param uniforms Matrix with one row per inspection and two independent
#'   U(0,1) columns, for true positives and false positives; reuse across scenarios.
#' @return Inspection counts of reported acceptable labels, without true counts.
misclassify_inspections <- function(clean, inventory, sensitivity, specificity, uniforms) {
  validate_inspection_counts(clean, inventory)
  invisible(inspection_label_probability(0.5, sensitivity, specificity))
  if (!is.matrix(uniforms) || !is.numeric(uniforms) ||
      !identical(dim(uniforms), c(nrow(clean), 2L)) ||
      any(!is.finite(uniforms)) || any(uniforms <= 0 | uniforms >= 1)) {
    stop("uniforms need two (0,1) columns and one row per inspection", call. = FALSE)
  }
  noisy <- clean[c("cohort", "day", "n_checked", "n_acceptable")]
  noisy$n_acceptable <- stats::qbinom(uniforms[, 1], clean$n_acceptable, sensitivity) +
    stats::qbinom(uniforms[, 2], clean$n_checked - clean$n_acceptable, 1 - specificity)
  noisy
}

#' Fit and choose a date from past reported labels and fixed calibration rates.
#' @param inspections Only reported inspection counts observed by decision_day.
#' @param inventory Initial mass/stratum inventory; supplied shapes/scales are
#'   overwritten placeholders and are not used as fitting starting values.
#' @param prices Forecast price grid.
#' @param sensitivity Fixed external sensitivity; one means the naive assumption.
#' @param specificity Fixed external specificity; one means the naive assumption.
#' @param decision_day Information cutoff and first sale date.
#' @param delivery_lag_days Delay until commercial acceptance.
#' @param storage_eur_per_kg_day Per-initial-kg daily holding cost.
#' @return Fitted true-acceptance curves and a chosen sale day, with no outcomes.
fit_inspection_policy <- function(inspections, inventory, prices, sensitivity = 1,
                                  specificity = 1, decision_day = 12L,
                                  delivery_lag_days = 2L, storage_eur_per_kg_day = 0.001) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  validate_inspections(inspections, inventory)
  if (any(inspections$day > decision_day)) {
    stop("fitting cannot use inspections after decision_day", call. = FALSE)
  }
  fitted <- with_fitted_survival(inventory,
    fit_weibull_by_cohort(inspections, inventory, sensitivity, specificity))
  selected <- optimal_batch_sale(fitted, prices, storage_eur_per_kg_day,
                                 decision_day, delivery_lag_days)
  list(inventory = fitted, sale_day = selected$sale_day)
}

#' Evaluate naive and correctly specified measurement-error fits on paired lots.
#' @param n_lots Independent synthetic lots, at least two.
#' @param simulation_seed Seed for true inventory, clean training counts and forecasts.
#' @param label_seed Separate seed for classification errors.
#' @param outcome_seed Separate seed for gold-standard holdouts and fruit outcomes.
#' @param scenarios Generating inspection rates, also supplied to the corrected fit.
#' @return One row per lot/scenario. All policies are fixed before outcomes are drawn.
run_inspection_error_experiment <- function(n_lots = 200L, simulation_seed = 20261028L,
                                           label_seed = 20261029L, outcome_seed = 20261030L,
                                           scenarios = default_inspection_scenarios()) {
  validate_inspection_scenarios(scenarios)
  for (name in c("n_lots", "simulation_seed", "label_seed", "outcome_seed")) {
    assert_nonnegative_scalar(get(name), name, integer = TRUE)
  }
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  set.seed(simulation_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    truth <- simulate_true_inventory()
    clean <- simulate_inspections(truth, c(3L, 6L, 9L, 12L))
    prices <- simulate_price_scenario(12L, 28L)
    list(lot_id = id, truth = truth, clean = clean, prices = prices)
  })
  set.seed(label_seed)
  policies <- lapply(lots, function(lot) {
    uniforms <- matrix(stats::runif(2L * nrow(lot$clean)), ncol = 2L)
    public_inventory <- transform(lot$truth, shape = 1, scale = 1)
    lapply(seq_len(nrow(scenarios)), function(i) {
      tryCatch({
        setting <- scenarios[i, ]
        noisy <- misclassify_inspections(lot$clean, public_inventory,
                                         setting$sensitivity, setting$specificity, uniforms)
        list(naive = fit_inspection_policy(noisy, public_inventory, lot$prices),
             corrected = fit_inspection_policy(noisy, public_inventory, lot$prices,
                                                setting$sensitivity, setting$specificity))
      }, error = function(error) {
        stop(sprintf("lot %d, scenario %s failed: %s", lot$lot_id, scenarios$scenario[i],
                     conditionMessage(error)), call. = FALSE)
      })
    })
  })
  # Future information does not exist until all fits and decisions are fixed.
  set.seed(outcome_seed)
  rows <- lapply(seq_along(lots), function(id) {
    lot <- lots[[id]]
    holdout <- simulate_inspections(lot$truth, c(16L, 20L, 24L), 250L)
    lifetimes <- simulate_fruit_lifetimes(lot$truth)
    evaluate <- function(day) realised_sale_value(day, lot$truth, lot$prices, lifetimes,
                                                  0.001, 12L, 2L)
    immediate <- evaluate(12L)
    do.call(rbind, lapply(seq_len(nrow(scenarios)), function(i) {
      row <- cbind(scenarios[i, , drop = FALSE], lot_id = id, realised_immediate_eur = immediate)
      for (name in c("naive", "corrected")) {
        policy <- policies[[id]][[i]][[name]]
        scores <- score_future_inspections(holdout, policy$inventory, 12L)
        row[[paste0("sale_day_", name)]] <- policy$sale_day
        row[[paste0("realised_", name, "_eur")]] <- evaluate(policy$sale_day)
        row[[paste0("brier_", name)]] <- scores$brier
        row[[paste0("log_loss_", name)]] <- scores$log_loss
      }
      row
    }))
  })
  records <- do.call(rbind, rows)
  rownames(records) <- NULL
  records
}

#' Summarise paired measurement-error correction effects; caller seeds the bootstrap.
#' @param records Complete output of run_inspection_error_experiment().
#' @param n_boot Number of whole-lot bootstrap resamples per contrast.
#' @return Means, marginal paired mean intervals and descriptive downside fractions.
summarize_inspection_error <- function(records, n_boot = 1000L) {
  fields <- c("sensitivity", "specificity", "lot_id", "realised_immediate_eur",
               "sale_day_naive", "sale_day_corrected", "realised_naive_eur",
               "realised_corrected_eur", "brier_naive", "brier_corrected",
               "log_loss_naive", "log_loss_corrected")
  if (!is.data.frame(records) || !all(c("scenario", fields) %in% names(records)) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1)))) {
    stop("records need finite rates, dates, scores and returns", call. = FALSE)
  }
  settings <- unique(records[c("scenario", "sensitivity", "specificity")])
  validate_inspection_scenarios(settings)
  if (anyDuplicated(records[c("scenario", "lot_id")]) ||
      length(unique(records$lot_id)) < 2L ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records need complete paired lot/scenario measurements", call. = FALSE)
  }
  for (id in unique(records$lot_id)) {
    if (length(unique(records$realised_immediate_eur[records$lot_id == id])) != 1L) {
      stop("inspection errors cannot change immediate-sale revenue", call. = FALSE)
    }
  }
  do.call(rbind, lapply(settings$scenario, function(name) {
    part <- records[records$scenario == name, ]
    row <- data.frame(scenario = name, n_lots = nrow(part),
                       different_sale_day_fraction = mean(part$sale_day_naive != part$sale_day_corrected))
    for (field in setdiff(fields, c("sensitivity", "specificity", "lot_id"))) {
      row[[paste0("mean_", field)]] <- mean(part[[field]])
    }
    differences <- list(
      brier_improvement = part$brier_naive - part$brier_corrected,
      log_loss_improvement = part$log_loss_naive - part$log_loss_corrected,
      corrected_minus_naive_eur = part$realised_corrected_eur - part$realised_naive_eur,
      corrected_minus_immediate_eur = part$realised_corrected_eur - part$realised_immediate_eur
    )
    for (contrast in names(differences)) {
      interval <- paired_lot_interval(differences[[contrast]], n_boot)
      for (statistic in names(interval)) {
        row[[paste0(contrast, "_", statistic)]] <- unname(interval[statistic])
      }
    }
    row$naive_below_immediate_fraction <- mean(part$realised_naive_eur < part$realised_immediate_eur)
    row$corrected_below_immediate_fraction <- mean(part$realised_corrected_eur < part$realised_immediate_eur)
    row
  }))
}
