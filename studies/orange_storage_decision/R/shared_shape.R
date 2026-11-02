# Source model.R and sampling.R first. Base R only.

#' Fit a common Weibull shape with a separate scale for each eligible stratum.
#'
#' For G strata this estimates G+1 parameters rather than 2G. The aggregated
#' binomial likelihood uses actual sample counts, with optional fixed inspection
#' sensitivity/specificity. This restriction can introduce bias when shapes differ.
#' @param inspections Independent aggregated inspection counts available for fitting.
#' @param cohorts Initial inventory metadata; supplied shapes/scales are not starts.
#' @param sensitivity Fixed inspection sensitivity, shared across strata and days.
#' @param specificity Fixed inspection specificity, shared across strata and days.
#' @return Data frame compatible with with_fitted_survival(), with identical shapes,
#'   stratum-specific scales and each stratum's negative log-likelihood contribution.
fit_shared_shape_weibull <- function(inspections, cohorts, sensitivity = 1, specificity = 1) {
  validate_inspections(inspections, cohorts)
  invisible(inspection_label_probability(0.5, sensitivity, specificity))
  groups <- sort(cohorts$cohort[cohorts$initially_sellable])
  if (length(groups) == 1L) {
    return(fit_weibull_by_cohort(inspections, cohorts, sensitivity, specificity))
  }
  observations <- inspections[order(match(inspections$cohort, groups), inspections$day), ]
  group_index <- match(observations$cohort, groups)
  minimum_day <- vapply(groups, function(g) min(observations$day[observations$cohort == g]), numeric(1))
  maximum_day <- vapply(groups, function(g) max(observations$day[observations$cohort == g]), numeric(1))
  contributions <- function(parameters) {
    p <- weibull_survival(observations$day, exp(parameters[1]),
                          exp(parameters[-1])[group_index])
    q <- inspection_label_probability(p, sensitivity, specificity)
    q <- pmin(1 - 1e-12, pmax(1e-12, q))
    -stats::dbinom(observations$n_acceptable, observations$n_checked, q, log = TRUE)
  }
  objective <- function(parameters) sum(contributions(parameters))
  lower <- log(c(0.25, minimum_day / 100))
  upper <- log(c(10, maximum_day * 100))
  starts <- list(log(c(1, maximum_day)), log(c(2, maximum_day * 2)),
                  log(c(4, maximum_day * 2)))
  candidates <- lapply(starts, function(start) {
    fit <- tryCatch(stats::optim(start, objective, method = "L-BFGS-B",
      lower = lower, upper = upper, control = list(maxit = 1000L)), error = function(e) NULL)
    if (!is.null(fit) && fit$convergence == 0L && is.finite(fit$value)) {
      return(list(par = fit$par, value = fit$value))
    }
    fallback <- tryCatch(stats::nlminb(start, objective, lower = lower, upper = upper,
      control = list(iter.max = 1000L, eval.max = 3000L)), error = function(e) NULL)
    if (!is.null(fallback) && fallback$convergence == 0L && is.finite(fallback$objective)) {
      return(list(par = fallback$par, value = fallback$objective))
    }
    NULL
  })
  candidates <- Filter(Negate(is.null), candidates)
  if (!length(candidates)) stop("shared-shape likelihood did not converge", call. = FALSE)
  best <- candidates[[which.min(vapply(candidates, `[[`, numeric(1), "value"))]]
  loss <- contributions(best$par)
  data.frame(cohort = groups, shape = exp(best$par[1]), scale = exp(best$par[-1]),
    negative_log_likelihood = vapply(seq_along(groups), function(i) sum(loss[group_index == i]), numeric(1)),
    row.names = NULL)
}
