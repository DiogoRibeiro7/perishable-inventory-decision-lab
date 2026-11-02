# Source model.R and sampling.R first. Calibration uses independent reference labels.

#' Estimate inspection accuracy from a reference-standard confusion table.
#' @param calibration Rows with day, true_positive, false_negative, true_negative,
#'   false_positive. Positive means commercially acceptable. Counts are independent
#'   of the storage inspections and reference labels are assumed correct.
#' @param decision_day Latest day on which reference observations may be available.
#' @return Pooled binomial estimates and reference sample sizes for each true class.
inspection_calibration_rates <- function(calibration, decision_day) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  fields <- c("day", "true_positive", "false_negative", "true_negative", "false_positive")
  if (!is.data.frame(calibration) || nrow(calibration) < 1L ||
      !all(fields %in% names(calibration)) ||
      any(!vapply(calibration[fields], function(x) {
        is.numeric(x) && all(is.finite(x)) && all(x >= 0 & x == floor(x))
      }, logical(1)))) {
    stop("calibration needs finite nonnegative whole-day and confusion counts", call. = FALSE)
  }
  if (any(calibration$day > decision_day)) {
    stop("calibration cannot use reference observations after decision_day", call. = FALSE)
  }
  n_acceptable <- sum(calibration$true_positive + calibration$false_negative)
  n_unacceptable <- sum(calibration$true_negative + calibration$false_positive)
  if (!is.finite(n_acceptable) || !is.finite(n_unacceptable) ||
      n_acceptable <= 0 || n_unacceptable <= 0) {
    stop("calibration needs observations in both true reference classes", call. = FALSE)
  }
  sensitivity <- sum(calibration$true_positive) / n_acceptable
  specificity <- sum(calibration$true_negative) / n_unacceptable
  invisible(inspection_label_probability(0.5, sensitivity, specificity))
  list(sensitivity = sensitivity, specificity = specificity,
       n_acceptable = n_acceptable, n_unacceptable = n_unacceptable)
}

#' Paired conditional and two-sample parametric bootstraps of the sale decision.
#'
#' Training label counts are generated from the original fitted curve and original
#' calibration estimates. Independent reference counts are generated from those
#' same original estimates; they change only the rates used at refitting. Generating
#' training labels from resampled rates would incorrectly couple the two samples.
#' Rates are common to all strata/days. This is a plug-in bootstrap, not a posterior.
#' @param inspections Reported storage inspections available by decision_day.
#' @param cohorts Initial inventory metadata; true survival is not used for fitting.
#' @param prices Forecast price grid.
#' @param calibration Independent reference confusion counts, available by decision_day.
#' @param storage_eur_per_kg_day Daily holding cost per initial eligible kg.
#' @param decision_day Information cutoff and first possible sale day.
#' @param delivery_lag_days Days between sale and acceptance.
#' @param prediction_day Fixed future day for acceptable-mass uncertainty.
#' @param n_boot Replicates per method; caller sets the RNG seed.
#' @return Point estimate, calibration estimates and one row per attempt/method.
#'   Invalid resampled calibration and failed refits are retained, never redrawn.
bootstrap_calibrated_sale <- function(inspections, cohorts, prices, calibration,
                                      storage_eur_per_kg_day, decision_day,
                                      delivery_lag_days = 0, prediction_day = 20L,
                                      n_boot = 500L) {
  rates <- inspection_calibration_rates(calibration, decision_day)
  validate_inspections(inspections, cohorts)
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  assert_nonnegative_scalar(prediction_day, "prediction_day", integer = TRUE)
  if (n_boot < 1L || any(inspections$day > decision_day) || prediction_day <= decision_day) {
    stop("bootstrap needs positive n_boot, past training and a future prediction_day", call. = FALSE)
  }
  fits <- fit_weibull_by_cohort(inspections, cohorts, rates$sensitivity, rates$specificity)
  evaluate <- function(fits) {
    inventory <- with_fitted_survival(cohorts, fits)
    selected <- optimal_batch_sale(inventory, prices, storage_eur_per_kg_day,
                                   decision_day, delivery_lag_days)
    eligible <- inventory[inventory$initially_sellable, ]
    data.frame(sale_day = selected$sale_day,
      acceptable_kg = sum(eligible$mass_kg *
        weibull_survival(rep(prediction_day, nrow(eligible)), eligible$shape, eligible$scale)))
  }
  point <- evaluate(fits) # Validate the price/cost contract before starting resamples.
  index <- match(inspections$cohort, fits$cohort)
  q <- inspection_label_probability(
    weibull_survival(inspections$day, fits$shape[index], fits$scale[index]),
    rates$sensitivity, rates$specificity)
  # Draw both independent samples before fitting; failures cannot shift later draws.
  training <- matrix(stats::rbinom(n_boot * nrow(inspections),
    rep(inspections$n_checked, each = n_boot), rep(q, each = n_boot)), nrow = n_boot)
  uniforms <- matrix(stats::runif(2L * n_boot), nrow = n_boot)
  sensitivity <- stats::qbinom(uniforms[, 1], rates$n_acceptable, rates$sensitivity) /
    rates$n_acceptable
  specificity <- stats::qbinom(uniforms[, 2], rates$n_unacceptable, rates$specificity) /
    rates$n_unacceptable
  draws <- lapply(seq_len(n_boot), function(iteration) {
    sampled <- inspections
    sampled$n_acceptable <- training[iteration, ]
    do.call(rbind, lapply(c("conditional", "recalibrated"), function(method) {
      se <- if (method == "conditional") rates$sensitivity else sensitivity[iteration]
      sp <- if (method == "conditional") rates$specificity else specificity[iteration]
      row <- data.frame(iteration = iteration, method = method, sensitivity = se,
        specificity = sp, status = "success", detail = "", sale_day = NA_real_,
        acceptable_kg = NA_real_)
      if (se + sp <= 1) {
        row$status <- "uninformative_calibration"
        row$detail <- "resampled sensitivity + specificity does not exceed one"
        return(row)
      }
      result <- tryCatch(evaluate(fit_weibull_by_cohort(sampled, cohorts, se, sp)),
                          error = function(error) error)
      if (inherits(result, "error")) {
        row$status <- "fit_failure"
        row$detail <- conditionMessage(result)
      } else {
        row$sale_day <- as.numeric(result$sale_day)
        row$acceptable_kg <- result$acceptable_kg
      }
      row
    }))
  })
  list(point_estimate = point, calibration = rates, prediction_day = prediction_day,
       draws = do.call(rbind, draws))
}

#' Summarise bootstrap distributions, explicitly accounting for all attempts.
#' @param draws A complete paired draw table from bootstrap_calibrated_sale().
#' @return Percentiles among successful replicates and counts of each failure type.
#'   These are parameter/decision uncertainty summaries, not validated coverage.
summarize_calibration_bootstrap <- function(draws) {
  fields <- c("iteration", "method", "status", "sale_day", "acceptable_kg")
  if (!is.data.frame(draws) || !all(fields %in% names(draws)) || nrow(draws) < 2L ||
      anyNA(draws[fields[1:3]]) ||
      !is.numeric(draws$iteration) || any(!is.finite(draws$iteration)) ||
      any(draws$iteration < 1 | draws$iteration != floor(draws$iteration)) ||
      !setequal(draws$method, c("conditional", "recalibrated")) ||
      anyDuplicated(draws[c("iteration", "method")]) ||
      any(table(draws$iteration) != 2L) ||
      any(!draws$status %in% c("success", "fit_failure", "uninformative_calibration"))) {
    stop("draws need complete paired iterations and recognised statuses", call. = FALSE)
  }
  success <- draws$status == "success"
  for (field in c("sale_day", "acceptable_kg")) {
    if (!is.numeric(draws[[field]]) || any(!is.finite(draws[[field]][success])) ||
        any(draws[[field]][success] < 0) || any(!is.na(draws[[field]][!success]))) {
      stop("successful draws need finite values; failed draws must have missing values", call. = FALSE)
    }
  }
  if (any(draws$sale_day[success] != floor(draws$sale_day[success]))) {
    stop("successful sale days must be whole numbers", call. = FALSE)
  }
  do.call(rbind, lapply(c("conditional", "recalibrated"), function(method) {
    part <- draws[draws$method == method, ]
    ok <- part$status == "success"
    row <- data.frame(method = method, attempted = nrow(part), successful = sum(ok),
      fit_failures = sum(part$status == "fit_failure"),
      calibration_failures = sum(part$status == "uninformative_calibration"),
      failed_fraction = mean(!ok))
    for (field in c("sale_day", "acceptable_kg")) {
      values <- part[[field]][ok]
      row[[paste0(field, "_mean")]] <- if (length(values)) mean(values) else NA_real_
      bounds <- if (length(values)) stats::quantile(values, c(0.025, 0.5, 0.975),
        names = FALSE, type = if (field == "sale_day") 1 else 7) else rep(NA_real_, 3)
      for (i in seq_along(bounds)) {
        row[[paste0(field, c("_lower_95", "_median", "_upper_95")[i])]] <- bounds[i]
      }
    }
    row
  }))
}
