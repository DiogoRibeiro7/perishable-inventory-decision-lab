# Source model, sampling, evaluation, simulation, price_sensitivity and
# robust_policy first. Policies retain their original Weibull extrapolations.

default_survival_scenarios <- function() {
  data.frame(scenario = c("unchanged", "slower", "faster", "double_hazard"),
              hazard_multiplier = c(1, 0.5, 1.5, 2), stringsAsFactors = FALSE)
}

validate_survival_scenarios <- function(scenarios) {
  if (!is.data.frame(scenarios) || nrow(scenarios) < 1L ||
      !all(c("scenario", "hazard_multiplier") %in% names(scenarios)) ||
      !is.character(scenarios$scenario) || anyNA(scenarios$scenario) ||
      any(!nzchar(trimws(scenarios$scenario))) || anyDuplicated(scenarios$scenario) ||
      !is.numeric(scenarios$hazard_multiplier) ||
      any(!is.finite(scenarios$hazard_multiplier)) || any(scenarios$hazard_multiplier <= 0)) {
    stop("scenarios need unique names and finite positive hazard multipliers", call. = FALSE)
  }
  invisible(TRUE)
}

#' Survival when the Weibull hazard changes by a fixed factor after a cutoff.
#' @param days Nonnegative evaluation times.
#' @param shape Positive Weibull shape, scalar or one per time.
#' @param scale Positive Weibull scale, scalar or one per time.
#' @param change_day Whole day when the hazard changes; survival is continuous.
#' @param hazard_multiplier Positive factor applied strictly after change_day.
#' @return Survival probabilities; original Weibull probabilities before change.
changed_hazard_survival <- function(days, shape, scale, change_day, hazard_multiplier) {
  original <- weibull_survival(days, shape, scale)
  assert_nonnegative_scalar(change_day, "change_day", integer = TRUE)
  assert_nonnegative_scalar(hazard_multiplier, "hazard_multiplier")
  if (hazard_multiplier == 0) stop("hazard_multiplier must be positive", call. = FALSE)
  if (hazard_multiplier == 1) return(original)
  total <- (days / scale)^shape
  before <- (pmin(days, change_day) / scale)^shape
  # Infinite cumulative hazard already implies zero survival for any positive
  # multiplier; avoid Inf - Inf when handling extreme but valid parameters.
  after <- days > change_day & is.finite(total)
  total[after] <- before[after] + hazard_multiplier * (total[after] - before[after])
  exp(-total)
}

#' Transform common fruit failure times to a changed-hazard potential outcome.
#' @param lifetimes Named vectors of finite nonnegative baseline failure times.
#' @param truth Initial inventory with hidden generating Weibull shapes.
#' @param change_day Whole-day change point.
#' @param hazard_multiplier Positive multiplier of the hazard after that point.
#' @return Named failure-time vectors, preserving fruit identity and pre-change failures.
stress_fruit_lifetimes <- function(lifetimes, truth, change_day, hazard_multiplier) {
  validate_cohorts(truth)
  assert_nonnegative_scalar(change_day, "change_day", integer = TRUE)
  assert_nonnegative_scalar(hazard_multiplier, "hazard_multiplier")
  if (hazard_multiplier == 0) stop("hazard_multiplier must be positive", call. = FALSE)
  eligible <- truth[truth$initially_sellable, ]
  if (!is.list(lifetimes) || anyDuplicated(names(lifetimes)) ||
      !setequal(names(lifetimes), eligible$cohort)) {
    stop("lifetimes must cover each eligible cohort exactly once", call. = FALSE)
  }
  for (times in lifetimes) {
    if (!is.numeric(times) || length(times) < 1L || any(!is.finite(times)) || any(times < 0)) {
      stop("fruit failure times must be finite and nonnegative", call. = FALSE)
    }
  }
  if (hazard_multiplier == 1) return(lifetimes)
  result <- lapply(names(lifetimes), function(group) {
    times <- lifetimes[[group]]
    shape <- eligible$shape[match(group, eligible$cohort)]
    after <- times > change_day
    fraction <- (change_day / times[after])^shape
    times[after] <- times[after] *
      (fraction + (1 - fraction) / hazard_multiplier)^(1 / shape)
    if (any(!is.finite(times))) stop("transformed failure times overflowed", call. = FALSE)
    times
  })
  names(result) <- names(lifetimes)
  result
}

#' Couple independent cross-sectional inspection counts across stress scenarios.
#' @param truth Hidden Weibull inventory before the change.
#' @param days Positive whole inspection days.
#' @param change_day Whole-day change point.
#' @param hazard_multiplier Positive post-change hazard factor.
#' @param uniforms Independent uniforms strictly between zero and one, one per
#'   cohort/day row in expand.grid order; reuse across scenarios for pairing.
#' @param per_group Fruit inspected per cohort/day.
#' @return Valid aggregate binomial counts with changed-hazard probabilities.
stress_inspections <- function(truth, days, change_day, hazard_multiplier,
                               uniforms, per_group = 250L) {
  validate_cohorts(truth)
  assert_nonnegative_scalar(per_group, "per_group", integer = TRUE)
  if (per_group < 1L || !is.numeric(days) || length(days) < 1L ||
      any(!is.finite(days)) || any(days <= 0 | days != floor(days)) || anyDuplicated(days)) {
    stop("inspection days and sample sizes must be positive whole numbers", call. = FALSE)
  }
  inspections <- expand.grid(cohort = truth$cohort[truth$initially_sellable], day = days,
                              KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  if (!is.numeric(uniforms) || length(uniforms) != nrow(inspections) ||
      any(!is.finite(uniforms)) || any(uniforms <= 0 | uniforms >= 1)) {
    stop("uniforms must be in (0, 1), one per cohort/day row", call. = FALSE)
  }
  position <- match(inspections$cohort, truth$cohort)
  probability <- changed_hazard_survival(inspections$day, truth$shape[position],
                                         truth$scale[position], change_day, hazard_multiplier)
  inspections$n_checked <- as.integer(per_group)
  inspections$n_acceptable <- stats::qbinom(uniforms, per_group, probability)
  inspections
}

#' Add signed inventory-standardised calibration error to proper holdout scores.
#' @param holdout Future binomial counts.
#' @param fitted_inventory Inventory with pre-cutoff fitted survival curves.
#' @param decision_day Information cutoff.
#' @return Brier, log loss, and bias (predicted minus observed acceptable fraction).
score_stress_inspections <- function(holdout, fitted_inventory, decision_day) {
  scores <- score_future_inspections(holdout, fitted_inventory, decision_day)
  position <- match(holdout$cohort, fitted_inventory$cohort)
  probability <- weibull_survival(holdout$day, fitted_inventory$shape[position],
                                  fitted_inventory$scale[position])
  weight <- inventory_sampling_weights(holdout, fitted_inventory)
  scores$bias <- sum(weight * (holdout$n_checked * probability - holdout$n_acceptable)) /
    sum(weight * holdout$n_checked)
  scores
}

#' Stress fixed policies under an unobserved day-12 hazard change.
#' @param n_lots Independent lots, at least two.
#' @param simulation_seed Seed for original prospective lots, fits and fruit draws.
#' @param inspection_seed Independent seed for new holdout counts; resets caller RNG.
#' @param scenarios Named post-cutoff hazard multipliers, never seen by policies.
#' @return One paired lot/scenario row with quality scores and realised net returns.
run_survival_stress <- function(n_lots = 200L, simulation_seed = 20261026L,
                                inspection_seed = 20261027L,
                                scenarios = default_survival_scenarios()) {
  validate_survival_scenarios(scenarios)
  assert_nonnegative_scalar(n_lots, "n_lots", integer = TRUE)
  assert_nonnegative_scalar(simulation_seed, "simulation_seed", integer = TRUE)
  assert_nonnegative_scalar(inspection_seed, "inspection_seed", integer = TRUE)
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  price_policy <- function(cohorts, prices, cost, day, lag) {
    means <- price_mean_scenarios(prices, cohorts, day, c(0.6, 0.8, 1))
    minimax_regret_sale(cohorts, means, cost, day, lag)$decision$sale_day
  }
  set.seed(simulation_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    tryCatch(simulate_policy_lot(id, additional_policy = price_policy),
             error = function(error) {
               stop(sprintf("synthetic lot %d failed: %s", id, conditionMessage(error)),
                    call. = FALSE)
             })
  })
  set.seed(inspection_seed)
  rows <- lapply(lots, function(lot) {
    days <- lot$decision_day + c(4L, 8L, 12L)
    uniforms <- stats::runif(sum(lot$truth$initially_sellable) * length(days))
    do.call(rbind, lapply(seq_len(nrow(scenarios)), function(i) {
      setting <- scenarios[i, , drop = FALSE]
      stressed <- lot
      stressed$lifetimes <- stress_fruit_lifetimes(
        lot$lifetimes, lot$truth, lot$decision_day, setting$hazard_multiplier
      )
      holdout <- stress_inspections(lot$truth, days, lot$decision_day,
                                    setting$hazard_multiplier, uniforms)
      stressed$stratified_score <- score_stress_inspections(holdout, lot$fitted_inventory,
                                                           lot$decision_day)
      stressed$pooled_score <- score_stress_inspections(holdout, lot$pooled_inventory,
                                                       lot$decision_day)
      scored <- score_policy_lot(stressed)
      # The original oracle assumes unchanged hazards and is not a valid oracle here.
      scored <- scored[, !grepl("oracle", names(scored)), drop = FALSE]
      scored$sale_day_robust <- lot$additional_day
      scored$realised_robust_eur <- realised_sale_value(
        lot$additional_day, lot$truth, lot$prices, stressed$lifetimes,
        lot$storage_eur_per_kg_day, lot$decision_day, lot$delivery_lag_days
      )
      scored$bias_stratified <- stressed$stratified_score$bias
      scored$bias_pooled <- stressed$pooled_score$bias
      cbind(setting, scored, row.names = NULL)
    }))
  })
  records <- do.call(rbind, rows)
  rownames(records) <- NULL
  records
}

#' Summarise calibration and paired returns under each deterioration scenario.
#' @param records Complete output of run_survival_stress().
#' @param n_boot Whole-lot bootstrap resamples per mean difference.
#' @return Scenario-level means, marginal mean intervals and descriptive downside.
summarize_survival_stress <- function(records, n_boot = 1000L) {
  fields <- c("hazard_multiplier", "lot_id", "sale_day_stratified", "sale_day_pooled",
               "sale_day_robust", "realised_stratified_eur", "realised_pooled_eur",
               "realised_robust_eur", "realised_immediate_eur", "brier_stratified",
               "brier_pooled", "log_loss_stratified", "log_loss_pooled",
               "bias_stratified", "bias_pooled")
  if (!is.data.frame(records) || !all(c("scenario", fields) %in% names(records)) ||
      any(!vapply(records[fields], function(x) {
        is.numeric(x) && all(is.finite(x))
      }, logical(1)))) {
    stop("records need finite numeric settings, dates, scores and returns", call. = FALSE)
  }
  settings <- unique(records[c("scenario", "hazard_multiplier")])
  validate_survival_scenarios(settings)
  if (anyDuplicated(records[c("scenario", "lot_id")]) ||
      length(unique(records$lot_id)) < 2L ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records need complete paired lot/scenario measurements", call. = FALSE)
  }
  dates <- c("sale_day_stratified", "sale_day_pooled", "sale_day_robust")
  for (id in unique(records$lot_id)) {
    if (nrow(unique(records[records$lot_id == id, dates])) != 1L) {
      stop("sale dates must be fixed across deterioration scenarios", call. = FALSE)
    }
  }
  do.call(rbind, lapply(settings$scenario, function(name) {
    part <- records[records$scenario == name, ]
    row <- data.frame(scenario = name, hazard_multiplier = part$hazard_multiplier[1],
                       n_lots = nrow(part))
    for (metric in c("brier_stratified", "brier_pooled", "log_loss_stratified",
                     "log_loss_pooled", "bias_stratified", "bias_pooled")) {
      row[[paste0("mean_", metric)]] <- mean(part[[metric]])
    }
    interval <- paired_lot_interval(part$bias_stratified, n_boot)
    row$bias_stratified_lower_95 <- unname(interval[2])
    row$bias_stratified_upper_95 <- unname(interval[3])
    for (policy in c("stratified", "pooled", "robust", "immediate")) {
      values <- part[[paste0("realised_", policy, "_eur")]]
      row[[paste0("mean_", policy, "_eur")]] <- mean(values)
      if (policy != "immediate") {
        difference <- values - part$realised_immediate_eur
        interval <- paired_lot_interval(difference, n_boot)
        for (statistic in names(interval)) {
          row[[paste0(policy, "_minus_immediate_", statistic, "_eur")]] <-
            unname(interval[statistic])
        }
        row[[paste0(policy, "_below_immediate_fraction")]] <- mean(difference < 0)
        row[[paste0(policy, "_minus_immediate_p10_eur")]] <-
          unname(stats::quantile(difference, 0.1))
      }
    }
    row
  }))
}
