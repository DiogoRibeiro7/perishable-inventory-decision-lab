#' Estimate stratum-specific commercial survival from inspection samples.
#'
#' Source R/model.R before loading this file. Inspections are independent
#' cross-sectional samples from each initially eligible cohort, not repeated
#' observations of a fixed panel of identified fruits.

#' Validate observed inspection counts without imposing fitting requirements.
#' @param inspections Data frame: cohort, day, n_checked, n_acceptable.
#' @param cohorts Initial inventory. Only initially saleable cohorts qualify.
validate_inspection_counts <- function(inspections, cohorts) {
  validate_cohorts(cohorts)
  required <- c("cohort", "day", "n_checked", "n_acceptable")
  if (!is.data.frame(inspections) || !all(required %in% names(inspections)) ||
      nrow(inspections) == 0L || !is.character(inspections$cohort) ||
      anyNA(inspections$cohort) || anyDuplicated(inspections[c("cohort", "day")])) {
    stop("inspections must have unique cohort/day rows and required columns",
         call. = FALSE)
  }
  for (column in c("day", "n_checked", "n_acceptable")) {
    values <- inspections[[column]]
    if (!is.numeric(values) || anyNA(values) || any(!is.finite(values)) ||
        any(values != floor(values)) || any(values < 0)) {
      stop(sprintf("%s must contain nonnegative whole numbers", column),
           call. = FALSE)
    }
  }
  if (any(inspections$day == 0) || any(inspections$n_checked == 0) ||
      any(inspections$n_acceptable > inspections$n_checked)) {
    stop("inspections need positive days and sample sizes, with valid counts",
         call. = FALSE)
  }
  groups <- cohorts$cohort[cohorts$initially_sellable]
  if (!setequal(unique(inspections$cohort), groups)) {
    stop("inspections must cover exactly the saleable cohorts", call. = FALSE)
  }
  invisible(TRUE)
}

#' Validate training inspections and require enough follow-up to fit a curve.
#' @param inspections Data frame: cohort, day, n_checked, n_acceptable.
#' @param cohorts Initial inventory. Only initially saleable cohorts qualify.
validate_inspections <- function(inspections, cohorts) {
  validate_inspection_counts(inspections, cohorts)
  groups <- cohorts$cohort[cohorts$initially_sellable]
  for (group in groups) {
    part <- inspections[inspections$cohort == group, , drop = FALSE]
    if (length(unique(part$day)) < 3L ||
        sum(part$n_acceptable) == 0 ||
        sum(part$n_checked - part$n_acceptable) == 0) {
      stop(sprintf("insufficient survival information for cohort %s", group),
           call. = FALSE)
    }
  }
  invisible(TRUE)
}

#' Probability an inspection labels a fruit acceptable, given its true state.
#' @param acceptable_probability True acceptable-fruit probabilities in [0, 1].
#' @param sensitivity P(label acceptable | truly acceptable), externally calibrated.
#' @param specificity P(label unacceptable | truly unacceptable), externally calibrated.
#' @return Observed-label probabilities. Rates are fixed, shared across observations,
#'   and must be informative in the stated label orientation (sum greater than one).
inspection_label_probability <- function(acceptable_probability, sensitivity = 1,
                                         specificity = 1) {
  for (name in c("sensitivity", "specificity")) {
    value <- if (name == "sensitivity") sensitivity else specificity
    assert_nonnegative_scalar(value, name)
    if (value > 1) stop(sprintf("%s must not exceed one", name), call. = FALSE)
  }
  if (sensitivity + specificity <= 1) {
    stop("sensitivity + specificity must exceed one", call. = FALSE)
  }
  p <- acceptable_probability
  if (!is.numeric(p) || length(p) < 1L || any(!is.finite(p)) || any(p < 0 | p > 1)) {
    stop("acceptable probabilities must be finite and in [0, 1]", call. = FALSE)
  }
  sensitivity * p + (1 - specificity) * (1 - p)
}

#' Robustly fit a two-parameter Weibull model to aggregated binomial counts.
#'
#' Start with bounded L-BFGS-B optimisation. If its line search terminates
#' unsuccessfully (which can happen for almost-flat likelihoods), retry with
#' independently bounded PORT optimisation, followed by alternate deterministic
#' starting points. A finite objective alone is *not* considered convergence.
#' This function does not impute or discard a difficult simulated lot.
#'
#' @param observations Valid subset of inspections for one or more groups.
#' @param weights Optional positive likelihood weights for pooled M-estimation.
#' @param sensitivity Known inspection sensitivity, shared across observations.
#' @param specificity Known inspection specificity, shared across observations.
#' @return Named list of Weibull shape, scale and minimised objective value.
estimate_weibull_binomial <- function(observations, weights = NULL,
                                      sensitivity = 1, specificity = 1) {
  invisible(inspection_label_probability(0.5, sensitivity, specificity))
  fields <- c("day", "n_checked", "n_acceptable")
  if (!is.data.frame(observations) || nrow(observations) < 1L ||
      !all(fields %in% names(observations))) {
    stop("observations need valid inspection count columns", call. = FALSE)
  }
  for (field in fields) {
    values <- observations[[field]]
    if (!is.numeric(values) || anyNA(values) ||
        any(!is.finite(values)) || any(values != floor(values))) {
      stop("inspection times and counts must be finite whole numbers",
           call. = FALSE)
    }
  }
  if (any(observations$day <= 0) ||
      any(observations$n_checked <= 0) ||
      any(observations$n_acceptable < 0) ||
      any(observations$n_acceptable > observations$n_checked)) {
    stop("inspection times and binomial counts are invalid", call. = FALSE)
  }
  if (is.null(weights)) {
    weights <- rep(1, nrow(observations))
  }
  if (!is.numeric(weights) || length(weights) != nrow(observations) ||
      anyNA(weights) || any(!is.finite(weights)) || any(weights <= 0)) {
    stop("weights must be finite strictly positive per observation",
         call. = FALSE)
  }

  objective <- function(log_parameters) {
    probability <- weibull_survival(
      observations$day, exp(log_parameters[1]), exp(log_parameters[2])
    )
    probability <- inspection_label_probability(probability, sensitivity, specificity)
    probability <- pmin(1 - 1e-12, pmax(1e-12, probability))
    -sum(weights * stats::dbinom(
      observations$n_acceptable, size = observations$n_checked,
      prob = probability, log = TRUE
    ))
  }
  lower <- log(c(0.25, min(observations$day) / 100))
  upper <- log(c(10, max(observations$day) * 100))
  starts <- list(
    log(c(2, stats::median(observations$day))),
    log(c(1, max(observations$day))),
    log(c(3, max(observations$day) / 2))
  )

  for (initial in starts) {
    attempt <- tryCatch(
      stats::optim(
        par = initial, fn = objective, method = "L-BFGS-B",
        lower = lower, upper = upper,
        control = list(maxit = 1000L)
      ),
      error = function(error) NULL
    )
    if (!is.null(attempt) && attempt$convergence == 0L &&
        is.finite(attempt$value)) {
      return(list(shape = exp(attempt$par[1]),
                  scale = exp(attempt$par[2]), objective = attempt$value))
    }

    # PORT uses a different bounded search; retry near any finite L-BFGS-B
    # solution, even if L-BFGS-B reported an unsuccessful line search.
    fallback_start <- if (!is.null(attempt) &&
                          all(is.finite(attempt$par))) attempt$par else initial
    fallback <- tryCatch(
      stats::nlminb(
        start = fallback_start, objective = objective,
        lower = lower, upper = upper,
        control = list(iter.max = 1000L, eval.max = 3000L)
      ),
      error = function(error) NULL
    )
    if (!is.null(fallback) && fallback$convergence == 0L &&
        is.finite(fallback$objective)) {
      return(list(shape = exp(fallback$par[1]),
                  scale = exp(fallback$par[2]),
                  objective = fallback$objective))
    }
  }

  stop("Weibull binomial objective did not converge after bounded retries",
       call. = FALSE)
}

#' Maximum-likelihood Weibull fits from cross-sectional binomial counts.
#'
#' Each observation is Binomial(n_checked, Se*S(day)+(1-Sp)*(1-S(day))).
#' Default Se=Sp=1 recovers the original perfect-inspection likelihood. The
#' fitted curves describe true commercial acceptance, not the noisy label.
#' Rates must come from separate calibration, not these same counts. A cohort is assumed
#' commercially acceptable at harvest; its membership cannot be inferred
#' using future measurements. Missing-at-random sampling and independence
#' within each inspection are modelling assumptions, not established facts.
#'
#' @param inspections Valid aggregated independent inspections.
#' @param cohorts Initial inventory with maturity strata.
#' @param sensitivity Known inspection sensitivity, common to all strata/days.
#' @param specificity Known inspection specificity, common to all strata/days.
#' @return Data frame of cohort, shape, scale, negative_log_likelihood.
fit_weibull_by_cohort <- function(inspections, cohorts, sensitivity = 1, specificity = 1) {
  validate_inspections(inspections, cohorts)
  groups <- cohorts$cohort[cohorts$initially_sellable]
  fits <- lapply(groups, function(group) {
    observations <- inspections[inspections$cohort == group, , drop = FALSE]
    result <- tryCatch(estimate_weibull_binomial(observations, sensitivity = sensitivity,
                                                specificity = specificity),
                       error = function(error) {
                         stop(sprintf("Weibull fit failed for %s: %s", group,
                                      conditionMessage(error)), call. = FALSE)
                       })
    data.frame(cohort = group, shape = result$shape,
               scale = result$scale,
               negative_log_likelihood = result$objective)
  })
  do.call(rbind, fits)
}

#' Replace prospective survival assumptions with fitted parameters.
#' @param cohorts Initial inventory (including ineligible groups).
#' @param fits Output of fit_weibull_by_cohort().
#' @return Validated inventory with the updated survival parameters.
with_fitted_survival <- function(cohorts, fits) {
  validate_cohorts(cohorts)
  if (!is.data.frame(fits) ||
      !all(c("cohort", "shape", "scale") %in% names(fits)) ||
      !is.character(fits$cohort) || anyNA(fits$cohort) ||
      anyDuplicated(fits$cohort)) {
    stop("fits must provide unique cohort, shape and scale values",
         call. = FALSE)
  }
  eligible <- which(cohorts$initially_sellable)
  if (!setequal(fits$cohort, cohorts$cohort[eligible])) {
    stop("fitted cohort labels do not match eligible inventory", call. = FALSE)
  }
  updated <- cohorts
  position <- match(updated$cohort[eligible], fits$cohort)
  updated$shape[eligible] <- fits$shape[position]
  updated$scale[eligible] <- fits$scale[position]
  validate_cohorts(updated)
  updated
}

#' Parametric bootstrap of the optimal whole-batch selling day.
#'
#' Counts are resampled from the fitted binomial inspection model and both
#' survival parameters and selling decisions are re-estimated. This measures
#' inspection-parameter uncertainty conditional on the Weibull model and on
#' the supplied price scenario and fixed inspection error rates; it does not
#' model uncertainty in external rate calibration, prices or weather.
#'
#' @param inspections Inspections observed no later than decision_day.
#' @param cohorts Inventory from which inspections were sampled.
#' @param prices Price scenarios for all initially saleable cohorts.
#' @param storage_eur_per_kg_day Per-kg daily holding cost.
#' @param decision_day Information cut-off and earliest sale day.
#' @param delivery_lag_days Days until quality is assessed at delivery.
#' @param n_boot Number of bootstrap attempts; caller controls the RNG seed.
#' @param sensitivity Known inspection sensitivity, used for simulation and refitting.
#' @param specificity Known inspection specificity, used for simulation and refitting.
#' @return List with decisions data frame, attempted, and failed counts.
bootstrap_sale_days <- function(inspections, cohorts, prices,
                                storage_eur_per_kg_day, decision_day,
                                delivery_lag_days = 0, n_boot = 100L,
                                sensitivity = 1, specificity = 1) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  if (n_boot < 1L || !is.numeric(inspections$day) ||
      anyNA(inspections$day) || any(inspections$day > decision_day)) {
    stop("bootstrap needs positive n_boot and no future inspections",
         call. = FALSE)
  }
  fits <- fit_weibull_by_cohort(inspections, cohorts, sensitivity, specificity)
  position <- match(inspections$cohort, fits$cohort)
  probability <- weibull_survival(inspections$day,
                                  fits$shape[position], fits$scale[position])
  probability <- inspection_label_probability(probability, sensitivity, specificity)

  results <- vector("list", n_boot)
  for (iteration in seq_len(n_boot)) {
    simulated <- inspections
    simulated$n_acceptable <- stats::rbinom(
      nrow(inspections), size = inspections$n_checked, prob = probability
    )
    # Report failed refits, rather than silently interpreting them as success.
    results[[iteration]] <- tryCatch({
      refitted <- fit_weibull_by_cohort(simulated, cohorts, sensitivity, specificity)
      selected <- optimal_batch_sale(
        with_fitted_survival(cohorts, refitted), prices,
        storage_eur_per_kg_day, decision_day, delivery_lag_days
      )
      data.frame(iteration = iteration, sale_day = selected$sale_day,
                 expected_net_eur = selected$expected_net_eur)
    }, error = function(error) NULL)
  }
  successful <- Filter(Negate(is.null), results)
  if (length(successful) == 0L) {
    stop("all bootstrap refits failed", call. = FALSE)
  }
  list(decisions = do.call(rbind, successful),
       attempted = n_boot, failed = n_boot - length(successful))
}
