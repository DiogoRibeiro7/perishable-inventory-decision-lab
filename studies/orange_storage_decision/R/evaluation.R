#' Out-of-time predictive scoring and a population-weighted pooled baseline.
#'
#' Source R/model.R and R/sampling.R before loading this file. Base R only.

#' Inventory-standardised weights for stratified inspection observations.
#'
#' Each inspection day receives its total observed sample size in weight, but
#' within that day strata receive weights proportional to eligible inventory
#' mass. This avoids bias towards an intentionally oversampled small stratum.
#' This is an M-estimation weight, not a claim of independent extra subjects.
#' Every day must include exactly one observation for each eligible stratum;
#' no missing-stratum outcomes or sample sizes are imputed by these weights.
#'
#' @param observations Aggregated observations with cohort, day, n_checked.
#' @param cohorts Initial inventory with initially_sellable and mass_kg.
#' @return Numeric nonnegative observation weights.
inventory_sampling_weights <- function(observations, cohorts) {
  validate_cohorts(cohorts)
  if (!is.data.frame(observations) ||
      nrow(observations) < 1L ||
      !all(c("cohort", "day", "n_checked") %in% names(observations)) ||
      !is.character(observations$cohort) || anyNA(observations$cohort) ||
      !is.numeric(observations$day) || anyNA(observations$day) ||
      any(!is.finite(observations$day)) ||
      any(observations$day <= 0 | observations$day != floor(observations$day)) ||
      !is.numeric(observations$n_checked) || anyNA(observations$n_checked) ||
      any(!is.finite(observations$n_checked)) ||
      any(observations$n_checked <= 0 |
          observations$n_checked != floor(observations$n_checked))) {
    stop("observations need valid cohorts, positive whole days and sample sizes",
         call. = FALSE)
  }
  if (anyDuplicated(observations[c("cohort", "day")])) {
    stop("each inspection cohort/day must occur exactly once",
         call. = FALSE)
  }
  eligible <- cohorts[cohorts$initially_sellable, , drop = FALSE]
  group_index <- match(observations$cohort, eligible$cohort)
  if (anyNA(group_index)) {
    stop("observations refer to an ineligible or unknown cohort",
         call. = FALSE)
  }
  if (any(table(observations$day) != nrow(eligible))) {
    stop("every inspection day must cover every eligible cohort",
         call. = FALSE)
  }
  mass_share <- eligible$mass_kg / sum(eligible$mass_kg)
  day_sizes <- ave(observations$n_checked, observations$day, FUN = sum)
  mass_share[group_index] * day_sizes / observations$n_checked
}

#' Estimate a single pooled Weibull curve, ignoring group-specific hazards.
#'
#' The mass-standardised weighted binomial objective represents a deliberately
#' restricted baseline: shape and scale are shared across all maturity groups.
#' It is generally misspecified if a population is a mixture of Weibulls.
#'
#' @param inspections Independent cross-sectional counts observed so far.
#' @param cohorts Initial mass/grade inventory.
#' @param sensitivity Known inspection sensitivity, shared across strata/days.
#' @param specificity Known inspection specificity, shared across strata/days.
#' @return List containing positive shape and scale and objective value.
fit_pooled_weibull <- function(inspections, cohorts, sensitivity = 1, specificity = 1) {
  validate_inspections(inspections, cohorts)
  weights <- inventory_sampling_weights(inspections, cohorts)
  estimate_weibull_binomial(inspections, weights, sensitivity, specificity)
}

#' Apply shared survival parameters to eligible inventory strata.
#' @param cohorts Initial inventory.
#' @param pooled Fit from fit_pooled_weibull().
#' @return Cohort inventory with identical survival parameters for eligible rows.
with_pooled_survival <- function(cohorts, pooled) {
  validate_cohorts(cohorts)
  if (!is.list(pooled) ||
      !all(c("shape", "scale") %in% names(pooled))) {
    stop("pooled must provide shape and scale", call. = FALSE)
  }
  for (name in c("shape", "scale")) {
    assert_nonnegative_scalar(pooled[[name]], name)
    if (pooled[[name]] == 0) {
      stop("pooled shape and scale must be strictly positive", call. = FALSE)
    }
  }
  updated <- cohorts
  selected <- updated$initially_sellable
  updated$shape[selected] <- pooled$shape
  updated$scale[selected] <- pooled$scale
  validate_cohorts(updated)
  updated
}

#' Score future inspections at the individual-fruit observation level.
#'
#' For aggregate Binomial(n, p), Brier score contributions are
#' y*(1-p)^2 + (n-y)*p^2, not (y/n-p)^2. Inventory standardisation makes
#' scores comparable when sampling fractions differ between maturity strata.
#' One future day and all-pass/all-fail observations are valid for scoring
#' existing predictions; curve-identification requirements apply only to fits.
#'
#' @param holdout Future, independent counts from initially eligible strata.
#' @param fitted_inventory Inventory with fitted survival parameters.
#' @param decision_day Fit information cut-off; all holdout days must exceed it.
#' @return Named list with Brier and log loss, both lower-is-better.
score_future_inspections <- function(holdout, fitted_inventory, decision_day) {
  validate_inspection_counts(holdout, fitted_inventory)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  if (any(holdout$day <= decision_day)) {
    stop("holdout inspections must occur strictly after decision_day",
         call. = FALSE)
  }
  index <- match(holdout$cohort, fitted_inventory$cohort)
  probability <- weibull_survival(
    holdout$day, fitted_inventory$shape[index], fitted_inventory$scale[index]
  )
  score_future_probabilities(holdout, fitted_inventory, probability, decision_day)
}

#' Score supplied true-acceptance probabilities aligned with future inspection rows.
#' @param holdout Independent future counts; all days must follow decision_day.
#' @param inventory Initial inventory used for mass-standardised scoring weights.
#' @param probability One true-acceptance probability per holdout row, in row order.
#' @param decision_day Information cutoff used to construct the predictions.
#' @return Brier and log loss at the individual-fruit level, both lower-is-better.
score_future_probabilities <- function(holdout, inventory, probability, decision_day) {
  validate_inspection_counts(holdout, inventory)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  if (any(holdout$day <= decision_day)) {
    stop("holdout inspections must occur strictly after decision_day", call. = FALSE)
  }
  if (!is.numeric(probability) || length(probability) != nrow(holdout) ||
      any(!is.finite(probability)) || any(probability < 0 | probability > 1)) {
    stop("probability needs one finite [0,1] value per holdout row", call. = FALSE)
  }
  probability <- pmin(1 - 1e-12, pmax(1e-12, probability))
  weight <- inventory_sampling_weights(holdout, inventory)
  positives <- holdout$n_acceptable
  negatives <- holdout$n_checked - positives
  weighted_n <- sum(weight * holdout$n_checked)

  list(
    brier = sum(weight * (positives * (1 - probability)^2 +
                           negatives * probability^2)) / weighted_n,
    log_loss = -sum(weight * (positives * log(probability) +
                              negatives * log1p(-probability))) / weighted_n
  )
}

#' Bootstrap the mean of independent, paired harvest-lot differences.
#'
#' @param differences Numeric vector of policy-A minus policy-B results.
#' @param n_boot Positive number of paired lot resamples.
#' @return Numeric vector of mean and percentile 95% interval endpoints.
paired_lot_interval <- function(differences, n_boot = 1000L) {
  if (!is.numeric(differences) || length(differences) < 2L ||
      anyNA(differences) || any(!is.finite(differences))) {
    stop("differences need two or more finite paired lot outcomes",
         call. = FALSE)
  }
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  if (n_boot < 1L) {
    stop("n_boot must be positive", call. = FALSE)
  }
  averages <- replicate(n_boot, mean(sample(differences, replace = TRUE)))
  bounds <- stats::quantile(averages, c(0.025, 0.975), names = FALSE)
  c(mean = mean(differences), lower_95 = bounds[1], upper_95 = bounds[2])
}
