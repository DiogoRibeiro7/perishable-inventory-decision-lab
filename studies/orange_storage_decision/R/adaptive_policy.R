# One optional future inspection in a finite-scenario Bayesian selling policy.
# Source model.R and sampling.R first. Base R only.
# These are predeclared hypotheses, NOT oracle parameters inferred from a lot.

validate_survival_scenarios <- function(scenarios) {
  labels <- names(scenarios)
  if (!is.list(scenarios) || is.data.frame(scenarios) || !length(scenarios) ||
      is.null(labels) || anyNA(labels) ||
      any(!nzchar(trimws(labels))) || anyDuplicated(labels)) {
    stop("scenarios must be a nonempty, uniquely named list", call. = FALSE)
  }
  lapply(scenarios, validate_cohorts)
  reference <- scenarios[[1]]
  for (inventory in scenarios[-1]) {
    index <- match(reference$cohort, inventory$cohort)
    if (anyNA(index) || nrow(inventory) != nrow(reference) ||
        !identical(inventory$initially_sellable[index], reference$initially_sellable) ||
        !isTRUE(all.equal(inventory$mass_kg[index], reference$mass_kg,
                          tolerance = 0))) {
      stop("scenarios must share cohort eligibility and observed initial mass",
           call. = FALSE)
    }
  }
  invisible(TRUE)
}

normalize_scenario_weights <- function(scenarios, weights) {
  validate_survival_scenarios(scenarios)
  if (!is.numeric(weights) || length(weights) != length(scenarios) ||
      anyNA(weights) || any(!is.finite(weights)) || any(weights < 0) ||
      !is.finite(sum(weights)) || sum(weights) <= 0 ||
      (!is.null(names(weights)) && !identical(names(weights), names(scenarios)))) {
    stop("weights must be finite nonnegative probabilities in scenario order",
         call. = FALSE)
  }
  stats::setNames(weights / sum(weights), names(scenarios))
}

#' Update a discrete survival-scenario posterior using NEW, observed counts.
#' All data must already exist by cutoff_day. Passing the same counts twice
#' would double-count them; callers must maintain disjoint observation batches.
scenario_posterior <- function(scenarios, weights, observations = NULL,
                               cutoff_day = 0L) {
  prior <- normalize_scenario_weights(scenarios, weights)
  assert_nonnegative_scalar(cutoff_day, "cutoff_day", integer = TRUE)
  if (is.null(observations)) return(prior)
  fields <- c("cohort", "day", "n_checked", "n_acceptable")
  if (!is.data.frame(observations) || !setequal(names(observations), fields)) {
    stop("observations must contain only aggregate inspection counts",
         call. = FALSE)
  }
  validate_inspection_counts(observations, scenarios[[1]])
  if (any(observations$day > cutoff_day)) {
    stop("future inspection counts cannot update the current posterior",
         call. = FALSE)
  }
  log_posterior <- log(unname(prior))
  for (i in seq_along(scenarios)) {
    inventory <- scenarios[[i]]
    index <- match(observations$cohort, inventory$cohort)
    p <- weibull_survival(observations$day,
                          inventory$shape[index], inventory$scale[index])
    log_posterior[i] <- log_posterior[i] + sum(stats::dbinom(
      observations$n_acceptable, observations$n_checked, p, log = TRUE
    ))
  }
  offset <- max(log_posterior)
  if (!is.finite(offset)) {
    stop("observations have zero probability under every scenario",
         call. = FALSE)
  }
  unnormalized <- exp(log_posterior - offset)
  stats::setNames(unnormalized / sum(unnormalized), names(scenarios))
}

#' Calculate the exact one-inspection value of information for a small library.
#'
#' At decision_day choose either a fixed future sale date (possibly today) or
#' commit to inspect at inspection_day, then choose a sale date >= that day.
#' Expected returns are anchored at decision_day in both alternatives.
#' An inspection is nondestructive and its direct labour cost is charged only
#' if ordered. All candidate prices are exogenous, known assumed forecasts.
#'
#' Outcome enumeration is exact conditional on this *finite, correctly
#' specified* survival-scenario library and independent binomial inspections.
#' It is not the value of arbitrary data collection or a general POMDP solver.
plan_adaptive_inspection <- function(scenarios, posterior, prices,
                                     storage_eur_per_kg_day, decision_day,
                                     inspection_day, checks_per_cohort = 8L,
                                     eur_per_check = 0.02,
                                     delivery_lag_days = 2L) {
  weights <- normalize_scenario_weights(scenarios, posterior)
  validate_prices(prices, scenarios[[1]])
  for (day in list(decision_day = decision_day, inspection_day = inspection_day,
                   delivery_lag_days = delivery_lag_days,
                   checks_per_cohort = checks_per_cohort)) {
    assert_nonnegative_scalar(day, "decision/inspection day or checks", integer = TRUE)
  }
  assert_nonnegative_scalar(storage_eur_per_kg_day, "storage_eur_per_kg_day")
  assert_nonnegative_scalar(eur_per_check, "eur_per_check")
  days <- sort(unique(prices$day))
  if (inspection_day <= decision_day || !(decision_day %in% days) ||
      !(inspection_day %in% days) || checks_per_cohort < 1L) {
    stop("require a later inspection day, available sale dates and positive checks",
         call. = FALSE)
  }
  n_groups <- sum(scenarios[[1]]$initially_sellable)
  if ((checks_per_cohort + 1)^n_groups > 5000) {
    stop("exact enumeration limited to 5000 joint count outcomes", call. = FALSE)
  }

  days <- days[days >= decision_day]
  values <- do.call(rbind, lapply(scenarios, function(inventory) {
    expected_value_grid(inventory, prices, storage_eur_per_kg_day,
                        decision_day, delivery_lag_days)$expected_net_eur
  }))
  dimnames(values) <- list(names(scenarios), as.character(days))
  fixed_values <- as.numeric(weights %*% values)
  fixed_index <- which.max(fixed_values) # earliest day wins ties

  groups <- scenarios[[1]]$cohort[scenarios[[1]]$initially_sellable]
  counts <- as.matrix(expand.grid(rep(list(seq.int(0L, checks_per_cohort)),
                                      n_groups), KEEP.OUT.ATTRS = FALSE))
  # Joint probability of each possible future sample under each scenario.
  joint <- matrix(0, nrow(counts), length(scenarios))
  for (i in seq_along(scenarios)) {
    inventory <- scenarios[[i]]
    index <- match(groups, inventory$cohort)
    p <- weibull_survival(rep(inspection_day, n_groups),
                          inventory$shape[index], inventory$scale[index])
    likelihood <- rep(1, nrow(counts))
    for (g in seq_along(groups)) {
      likelihood <- likelihood * stats::dbinom(counts[, g], checks_per_cohort, p[g])
    }
    joint[, i] <- weights[i] * likelihood
  }
  predictive_probability <- rowSums(joint)
  possible <- predictive_probability > 0
  future_index <- which(days >= inspection_day)
  updated <- joint[possible, , drop = FALSE] /
    predictive_probability[possible]
  updated_value <- updated %*% values[, future_index, drop = FALSE]
  before_labour <- sum(predictive_probability[possible] *
                         apply(updated_value, 1, max))
  labour <- checks_per_cohort * n_groups * eur_per_check
  inspected_value <- before_labour - labour
  fixed_value <- fixed_values[fixed_index]

  list(action = if (inspected_value > fixed_value + 1e-9) "inspect" else "commit",
       fixed_day = days[fixed_index], fixed_expected_eur = fixed_value,
       inspection_expected_eur = inspected_value,
       gross_information_value_eur = before_labour - fixed_value,
       net_information_value_eur = inspected_value - fixed_value,
       inspection_labour_eur = labour, checks_per_cohort = checks_per_cohort,
       inspection_day = inspection_day, decision_day = decision_day,
       days = days, values = values, posterior = weights, scenarios = scenarios)
}

#' After a chosen inspection, reoptimise using only its newly arrived labels.
#' A no-inspection comparator can use the same hypothetical inspection to
#' score an always-inspect policy, but not to change its precommitted day.
sale_after_inspection <- function(plan, observations) {
  fields <- c("cohort", "day", "n_checked", "n_acceptable")
  groups <- plan$scenarios[[1]]$cohort[
    plan$scenarios[[1]]$initially_sellable]
  if (!is.data.frame(observations) || !setequal(names(observations), fields)) {
    stop("follow-up must contain only aggregate inspection counts", call. = FALSE)
  }
  validate_inspection_counts(observations, plan$scenarios[[1]])
  if (nrow(observations) != length(groups) ||
      any(observations$day != plan$inspection_day) ||
      any(observations$n_checked != plan$checks_per_cohort)) {
    stop("follow-up counts must match the prespecified inspection plan",
         call. = FALSE)
  }
  weights <- scenario_posterior(plan$scenarios, plan$posterior,
                                observations, plan$inspection_day)
  available <- which(plan$days >= plan$inspection_day)
  expected <- as.numeric(weights %*% plan$values[, available, drop = FALSE])
  index <- which.max(expected)
  list(sale_day = plan$days[available[index]], posterior = weights,
       expected_net_eur = expected[index])
}
