# Prospective, paired evaluation of the one-inspection policy.
# Source model.R, sampling.R, simulation.R and adaptive_policy.R first.

#' Three prespecified, market-eligible survival hypotheses.
#' The initial grade masses are observed. Only the survival scales differ.
#' The scenario library is deliberately defined without a target lot's truth.
adaptive_scenario_library <- function(advanced_kg) {
  if (!is.numeric(advanced_kg) || length(advanced_kg) != 1L ||
      !is.finite(advanced_kg) || advanced_kg <= 0 || advanced_kg >= 850) {
    stop("advanced_kg must lie strictly between zero and 850", call. = FALSE)
  }
  inventory <- data.frame(
    cohort = c("advanced", "intermediate", "initially_immature"),
    mass_kg = c(advanced_kg, 850 - advanced_kg, 150),
    initially_sellable = c(TRUE, TRUE, FALSE),
    shape = c(2.2, 1.8, 1), scale = c(18, 36, 1),
    stringsAsFactors = FALSE
  )
  scales <- c(short = 0.70, typical = 1, long = 1.35)
  lapply(scales, function(factor) {
    scenario <- inventory
    scenario$scale[scenario$initially_sellable] <-
      scenario$scale[scenario$initially_sellable] * factor
    scenario
  })
}

#' Simulate one target lot. The latent scenario is never passed to the policy.
#' Both the never-inspect and always-inspect comparators use the same lot,
#' predecision counts, exogenous price path, future sample and fruit lifetimes.
simulate_adaptive_lot <- function(lot_id, weights = c(short = 0.3,
                                                       typical = 0.4,
                                                       long = 0.3),
                                   eur_per_check = 0.02,
                                   checks_per_cohort = 8L) {
  assert_nonnegative_scalar(lot_id, "lot_id", integer = TRUE)
  if (lot_id < 1L) stop("lot_id must be positive", call. = FALSE)
  scenarios <- adaptive_scenario_library(850 * stats::runif(1, 0.25, 0.60))
  prior <- normalize_scenario_weights(scenarios, weights)
  scenario_id <- sample.int(length(scenarios), 1L, prob = prior)
  truth <- scenarios[[scenario_id]]
  prices <- simulate_price_scenario(12L, 28L)

  # Counts are independent, representative, NONDESTRUCTIVE inspections.
  # The true scenario and hidden fruit outcomes are absent from these inputs.
  historical_counts <- simulate_inspections(truth, c(6L, 12L), 6L)
  posterior <- scenario_posterior(scenarios, prior, historical_counts, 12L)
  plan <- plan_adaptive_inspection(scenarios, posterior, prices,
                                   storage_eur_per_kg_day = 0.001,
                                   decision_day = 12L, inspection_day = 16L,
                                   checks_per_cohort = checks_per_cohort,
                                   eur_per_check = eur_per_check,
                                   delivery_lag_days = 2L)

  # The day-16 sample is generated only AFTER the day-12 plan is frozen.
  # It is a potential observation for the always-inspect comparator even when
  # the adaptive policy has already committed to a date without inspecting.
  future_counts <- simulate_inspections(truth, 16L, checks_per_cohort)
  followup_day <- sale_after_inspection(plan, future_counts)$sale_day
  adaptive_day <- if (plan$action == "inspect") followup_day else plan$fixed_day

  # Outcomes are sampled only after every compared sale day is fixed.
  lifetimes <- simulate_fruit_lifetimes(truth)
  realised <- function(day) {
    realised_sale_value(day, truth, prices, lifetimes, 0.001, 12L, 2L)
  }
  labour <- plan$inspection_labour_eur
  data.frame(
    lot_id = lot_id, generating_scenario = names(scenarios)[scenario_id],
    action = plan$action, fixed_day = plan$fixed_day,
    adaptive_day = adaptive_day, always_inspect_day = followup_day,
    net_information_value_eur = plan$net_information_value_eur,
    labour_if_inspected_eur = labour,
    fixed_eur = realised(plan$fixed_day),
    immediate_eur = realised(12L),
    always_inspect_eur = realised(followup_day) - labour,
    adaptive_eur = realised(adaptive_day) -
      if (plan$action == "inspect") labour else 0,
    stringsAsFactors = FALSE
  )
}

#' Reproducible paired synthetic experiment; the RNG seed is explicit.
run_adaptive_experiment <- function(n_lots = 100L, seed = 20261101L,
                                    eur_per_check = 0.02,
                                    checks_per_cohort = 8L) {
  assert_nonnegative_scalar(n_lots, "n_lots", integer = TRUE)
  assert_nonnegative_scalar(seed, "seed", integer = TRUE)
  if (n_lots < 2L) stop("at least two independent lots required", call. = FALSE)
  set.seed(seed)
  do.call(rbind, lapply(seq_len(n_lots), function(i) {
    simulate_adaptive_lot(i, eur_per_check = eur_per_check,
                          checks_per_cohort = checks_per_cohort)
  }))
}

#' Whole-lot paired bootstrap intervals, preserving correlated policies.
#' Do not treat simulated fruit or multiple policy returns as independent lots.
summarize_adaptive_experiment <- function(records, n_boot = 1000L) {
  fields <- c("lot_id", "action", "fixed_eur", "immediate_eur",
              "adaptive_eur", "always_inspect_eur")
  if (!is.data.frame(records) || !all(fields %in% names(records)) ||
      nrow(records) < 2L || anyDuplicated(records$lot_id) ||
      anyNA(records[fields]) ||
      any(!records$action %in% c("commit", "inspect")) ||
      any(!is.finite(as.matrix(records[c("fixed_eur", "immediate_eur",
                                         "adaptive_eur", "always_inspect_eur")])))) {
    stop("records must contain distinct lots and finite paired returns",
         call. = FALSE)
  }
  assert_nonnegative_scalar(n_boot, "n_boot", integer = TRUE)
  if (n_boot < 1L) stop("n_boot must be positive", call. = FALSE)
  differences <- list(adaptive_vs_fixed = records$adaptive_eur - records$fixed_eur,
                      adaptive_vs_immediate = records$adaptive_eur - records$immediate_eur,
                      always_inspect_vs_fixed = records$always_inspect_eur - records$fixed_eur)
  do.call(rbind, lapply(names(differences), function(label) {
    gain <- differences[[label]]
    means <- replicate(n_boot, mean(sample(gain, replace = TRUE)))
    data.frame(comparison = label, n_lots = length(gain),
               inspected_fraction = mean(records$action == "inspect"),
               mean_gain_eur = mean(gain),
               lower_95_eur = unname(stats::quantile(means, 0.025)),
               upper_95_eur = unname(stats::quantile(means, 0.975)),
               fraction_below_baseline = mean(gain < 0),
               row.names = NULL)
  }))
}
