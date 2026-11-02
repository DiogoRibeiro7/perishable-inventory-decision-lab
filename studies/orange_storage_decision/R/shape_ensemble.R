# Source model.R, sampling.R and shared_shape.R first. No external packages.

#' Exponential model weights from comparable maximum-likelihood AIC scores.
#' @param negative_log_likelihood Finite nonnegative losses on the same data.
#' @param parameters Positive whole-number counts of fitted parameters.
#' @return Named columns for AIC, delta AIC and normalised weights.
aic_shape_weights <- function(negative_log_likelihood, parameters) {
  if (!is.numeric(negative_log_likelihood) || length(negative_log_likelihood) < 1L ||
      any(!is.finite(negative_log_likelihood)) || any(negative_log_likelihood < 0) ||
      !is.numeric(parameters) || length(parameters) != length(negative_log_likelihood) ||
      any(!is.finite(parameters)) || any(parameters <= 0 | parameters != floor(parameters))) {
    stop("AIC needs finite binomial losses and positive parameter counts", call. = FALSE)
  }
  aic <- 2 * negative_log_likelihood + 2 * parameters
  if (any(!is.finite(aic))) stop("AIC overflow", call. = FALSE)
  delta <- aic - min(aic)
  relative <- exp(-0.5 * delta)
  data.frame(aic = aic, delta_aic = delta, weight = relative / sum(relative))
}

# Internal constructor: both fits must use the same training rows, likelihood
# constants and fixed calibration rates. Public fitting and the study enforce this.
assemble_shape_ensemble <- function(fits, inventory, decision_day) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  validate_cohorts(inventory)
  groups <- sum(inventory$initially_sellable)
  models <- c("separate", "shared")
  if (!is.list(fits) || !setequal(names(fits), models)) {
    stop("both component fits are required", call. = FALSE)
  }
  for (name in models) {
    loss <- fits[[name]]$negative_log_likelihood
    if (!is.data.frame(fits[[name]]) || !is.numeric(loss) || length(loss) != groups ||
        any(!is.finite(loss)) || any(loss < 0)) {
      stop("component fits need finite binomial likelihood contributions", call. = FALSE)
    }
  }
  losses <- vapply(models, function(name) sum(fits[[name]]$negative_log_likelihood), numeric(1))
  counts <- c(2 * groups, groups + 1)
  comparison <- cbind(data.frame(model = models, parameters = counts,
    negative_log_likelihood = unname(losses)), aic_shape_weights(losses, counts))
  inventories <- lapply(fits[models], function(fit) with_fitted_survival(inventory, fit))
  list(inventories = inventories, fits = fits[models], weights = stats::setNames(comparison$weight, models),
       comparison = comparison, decision_day = decision_day)
}

# The shared fit is a feasible point for each unrestricted stratum. Retry any
# separate fit whose loss is worse, using that feasible point as a warm start.
# This changes only the ensemble's component fits, not the original fitter.
refine_ensemble_separate <- function(inspections, separate, shared, sensitivity, specificity) {
  for (i in seq_len(nrow(separate))) {
    j <- match(separate$cohort[i], shared$cohort)
    if (separate$negative_log_likelihood[i] <= shared$negative_log_likelihood[j] + 1e-8) next
    observations <- inspections[inspections$cohort == separate$cohort[i], ]
    objective <- function(parameters) {
      p <- weibull_survival(observations$day, exp(parameters[1]), exp(parameters[2]))
      q <- inspection_label_probability(p, sensitivity, specificity)
      q <- pmin(1 - 1e-12, pmax(1e-12, q))
      -sum(stats::dbinom(observations$n_acceptable, observations$n_checked, q, log = TRUE))
    }
    fit <- stats::nlminb(log(c(shared$shape[j], shared$scale[j])), objective,
      lower = log(c(0.25, min(observations$day) / 100)),
      upper = log(c(10, max(observations$day) * 100)),
      control = list(iter.max = 1000L, eval.max = 3000L))
    if (fit$convergence != 0L || !is.finite(fit$objective) ||
        fit$objective > shared$negative_log_likelihood[j] + 1e-8) {
      stop("separate component could not improve its feasible shared-shape start", call. = FALSE)
    }
    separate$shape[i] <- exp(fit$par[1])
    separate$scale[i] <- exp(fit$par[2])
    separate$negative_log_likelihood[i] <- fit$objective
  }
  separate
}

#' Fit and weight separate/shared Weibull models using only pre-cutoff inspections.
#' @param inspections Reported inspection counts available by decision_day.
#' @param inventory Initial inventory metadata; true survival parameters are not used.
#' @param decision_day Information cutoff and first candidate sale date.
#' @param sensitivity Fixed inspection sensitivity, shared by both likelihoods.
#' @param specificity Fixed inspection specificity, shared by both likelihoods.
#' @return Fitted component inventories, training-only weights and AIC diagnostics.
fit_shape_ensemble <- function(inspections, inventory, decision_day,
                                sensitivity = 1, specificity = 1) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  validate_inspections(inspections, inventory)
  if (any(inspections$day > decision_day)) stop("ensemble cannot use future inspections", call. = FALSE)
  fits <- list(separate = fit_weibull_by_cohort(inspections, inventory, sensitivity, specificity),
               shared = fit_shared_shape_weibull(inspections, inventory, sensitivity, specificity))
  fits$separate <- refine_ensemble_separate(inspections, fits$separate, fits$shared,
                                            sensitivity, specificity)
  assemble_shape_ensemble(fits, inventory, decision_day)
}

validate_shape_ensemble <- function(model) {
  names_expected <- c("separate", "shared")
  if (!is.list(model) || !is.list(model$inventories) ||
      !identical(names(model$inventories), names_expected) ||
      !is.numeric(model$weights) || !identical(names(model$weights), names_expected) ||
      length(model$weights) != 2L || any(!is.finite(model$weights)) ||
      any(model$weights < 0 | model$weights > 1) || abs(sum(model$weights) - 1) > 1e-12) {
    stop("ensemble needs two named inventories and nonnegative weights summing to one", call. = FALSE)
  }
  assert_nonnegative_scalar(model$decision_day, "decision_day", integer = TRUE)
  metadata <- lapply(model$inventories, function(inventory) {
    validate_cohorts(inventory)
    part <- inventory[order(inventory$cohort), c("cohort", "mass_kg", "initially_sellable")]
    rownames(part) <- NULL
    part
  })
  if (!isTRUE(all.equal(metadata[[1]], metadata[[2]], tolerance = 0))) {
    stop("ensemble components must describe the same inventory", call. = FALSE)
  }
  invisible(TRUE)
}

#' Average true survival probabilities, rather than Weibull parameters or sale dates.
#' @param model Output of fit_shape_ensemble().
#' @param cohort Eligible stratum labels, one per requested probability.
#' @param day Nonnegative finite days, one per stratum label; no implicit recycling.
#' @return Numeric mixture survival probabilities in the requested order.
predict_shape_ensemble <- function(model, cohort, day) {
  validate_shape_ensemble(model)
  if (!is.character(cohort) || length(cohort) < 1L || anyNA(cohort) ||
      !is.numeric(day) || length(day) != length(cohort) || any(!is.finite(day)) || any(day < 0)) {
    stop("prediction needs aligned cohort labels and nonnegative finite days", call. = FALSE)
  }
  probability <- lapply(model$inventories, function(inventory) {
    eligible <- inventory[inventory$initially_sellable, ]
    index <- match(cohort, eligible$cohort)
    if (anyNA(index)) stop("prediction refers to an ineligible or unknown stratum", call. = FALSE)
    weibull_survival(day, eligible$shape[index], eligible$scale[index])
  })
  unname(model$weights[1] * probability[[1]] + model$weights[2] * probability[[2]])
}

#' Expected values under the survival mixture and one common future price path.
ensemble_value_grid <- function(model, prices, storage_eur_per_kg_day, delivery_lag_days = 0) {
  validate_shape_ensemble(model)
  grids <- lapply(model$inventories, function(inventory) {
    expected_value_grid(inventory, prices, storage_eur_per_kg_day,
                         model$decision_day, delivery_lag_days)
  })
  result <- grids[[1]]
  for (field in c("expected_sellable_kg", "expected_gross_eur", "additional_storage_eur", "expected_net_eur")) {
    result[[field]] <- model$weights[1] * grids[[1]][[field]] + model$weights[2] * grids[[2]][[field]]
  }
  result
}

#' Choose the earliest maximum of the averaged value curve, not an average date.
optimal_ensemble_sale <- function(...) {
  grid <- ensemble_value_grid(...)
  grid[which.max(grid$expected_net_eur), , drop = FALSE]
}

# Builder for run_shared_shape_experiment(); reuses its already fitted components.
shape_ensemble_policy <- function(inspections, inventory, prices, policies) {
  if (any(inspections$day > 12L)) stop("ensemble study cannot use future inspections", call. = FALSE)
  model <- assemble_shape_ensemble(lapply(policies, `[[`, "fits"), inventory, 12L)
  list(sale_day = optimal_ensemble_sale(model, prices, 0.001, 2L)$sale_day,
       predict = function(cohort, day) predict_shape_ensemble(model, cohort, day),
       diagnostics = c(weight_shared = unname(model$weights["shared"]),
         nll_separate = model$comparison$negative_log_likelihood[1],
         nll_shared = model$comparison$negative_log_likelihood[2]))
}

# Both the separate benchmark and its ensemble component use the refined fit.
fit_ensemble_shape_policy <- function(inspections, inventory, prices, method) {
  if (method == "shared") return(fit_shape_policy(inspections, inventory, prices, method))
  if (method != "separate") stop("unknown component model", call. = FALSE)
  model <- fit_shape_ensemble(inspections, inventory, 12L, 0.9, 0.9)
  fitted <- model$inventories$separate
  list(inventory = fitted, fits = model$fits$separate,
       sale_day = optimal_batch_sale(fitted, prices, 0.001, 12L, 2L)$sale_day)
}

#' Evaluate the training-weighted mixture on fresh paired lots and shape regimes.
#' @param n_lots Number of independent base lots, at least two.
#' @param training_seed Seed for prospective inventory, prices and training counts.
#' @param outcome_seed Separate seed for future inspections and fruit lifetimes.
#' @param scenarios Prespecified shape regimes, not used to select model weights.
#' @param training_per_group Positive inspection count per stratum and training day.
#' @return Paired component/ensemble predictions, returns and training diagnostics.
run_shape_ensemble_experiment <- function(n_lots = 200L, training_seed = 20261104L,
                                          outcome_seed = 20261105L,
                                          scenarios = default_shape_scenarios(),
                                          training_per_group = 180L) {
  records <- run_shared_shape_experiment(n_lots, training_seed, outcome_seed, scenarios,
    additional_policy = shape_ensemble_policy, policy_fitter = fit_ensemble_shape_policy,
    training_per_group = training_per_group)
  names(records) <- sub("^additional_", "ensemble_", names(records))
  names(records) <- sub("_additional", "_ensemble", names(records))
  records
}

#' Summarise paired contrasts with each component and immediate sale.
summarize_shape_ensemble <- function(records, n_boot = 1000L) {
  fields <- c("lot_id", "realised_immediate_eur", "ensemble_weight_shared")
  for (model in c("separate", "shared", "ensemble")) {
    fields <- c(fields, paste0("sale_day_", model), paste0("realised_", model, "_eur"),
                paste0("brier_", model), paste0("log_loss_", model))
  }
  if (!is.data.frame(records) || !all(c("scenario", fields) %in% names(records)) ||
      !is.character(records$scenario) || anyNA(records$scenario) ||
      any(!nzchar(trimws(records$scenario))) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1))) ||
      any(records$ensemble_weight_shared < 0 | records$ensemble_weight_shared > 1) ||
      anyDuplicated(records[c("lot_id", "scenario")]) || length(unique(records$lot_id)) < 2L ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records need complete, finite, paired lot/scenario measurements", call. = FALSE)
  }
  do.call(rbind, lapply(unique(records$scenario), function(scenario) {
    part <- records[records$scenario == scenario, ]
    row <- data.frame(scenario = scenario, n_lots = nrow(part))
    for (field in setdiff(fields, "lot_id")) row[[paste0("mean_", field)]] <- mean(part[[field]])
    differences <- list(ensemble_minus_immediate_eur = part$realised_ensemble_eur - part$realised_immediate_eur)
    for (model in c("separate", "shared")) {
      differences[[paste0("ensemble_minus_", model, "_eur")]] <-
        part$realised_ensemble_eur - part[[paste0("realised_", model, "_eur")]]
      differences[[paste0("brier_improvement_vs_", model)]] <-
        part[[paste0("brier_", model)]] - part$brier_ensemble
      differences[[paste0("log_loss_improvement_vs_", model)]] <-
        part[[paste0("log_loss_", model)]] - part$log_loss_ensemble
    }
    for (contrast in names(differences)) {
      interval <- paired_lot_interval(differences[[contrast]], n_boot)
      for (statistic in names(interval)) row[[paste0(contrast, "_", statistic)]] <- unname(interval[statistic])
    }
    for (model in c("separate", "shared", "ensemble")) {
      row[[paste0(model, "_below_immediate_fraction")]] <-
        mean(part[[paste0("realised_", model, "_eur")]] < part$realised_immediate_eur)
    }
    row$shared_weight_above_half_fraction <- mean(part$ensemble_weight_shared > 0.5)
    row
  }))
}
