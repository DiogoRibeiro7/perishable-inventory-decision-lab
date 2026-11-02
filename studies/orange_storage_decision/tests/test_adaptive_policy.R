# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/simulation.R")
source("R/adaptive_policy.R")
source("R/adaptive_evaluation.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(e) TRUE))
}

# A hand-checked one-cohort example: fast decay favours day 2 and slow decay
# favours day 3. Day 1 has zero price, so an optional day-2 inspection has
# positive value when cheap enough, but should be rejected when costly.
fast <- data.frame(cohort = "a", mass_kg = 100,
                   initially_sellable = TRUE, shape = 1, scale = 3)
slow <- transform(fast, scale = 100)
scenarios <- list(fast = fast, slow = slow)
prices <- data.frame(cohort = "a", day = 1:3,
                     price_eur_per_kg = c(0, 1, 1.3))
prior <- c(fast = 0.5, slow = 0.5)
cheap <- plan_adaptive_inspection(scenarios, prior, prices, 0, 1, 2,
                                  checks_per_cohort = 10, eur_per_check = 0)
expensive <- plan_adaptive_inspection(scenarios, prior, prices, 0, 1, 2,
                                      checks_per_cohort = 10, eur_per_check = 100)
stopifnot(cheap$fixed_day == 3L, cheap$action == "inspect",
          cheap$net_information_value_eur > 0,
          expensive$action == "commit", expensive$fixed_day == 3L,
          abs(expensive$net_information_value_eur -
                (cheap$net_information_value_eur - 1000)) < 1e-9)

followup <- data.frame(cohort = "a", day = 2L,
                       n_checked = 10L, n_acceptable = 0L)
after_failures <- sale_after_inspection(cheap, followup)
followup$n_acceptable <- 10L
after_successes <- sale_after_inspection(cheap, followup)
stopifnot(after_failures$sale_day == 2L, after_successes$sale_day == 3L,
          after_successes$posterior["slow"] > after_failures$posterior["slow"])

# Bayes rule is calculated from independent binomial likelihoods, not fitted
# latent truth or outcomes from after the explicit information cutoff.
one <- data.frame(cohort = "a", day = 2L,
                  n_checked = 1L, n_acceptable = 1L)
posterior <- scenario_posterior(scenarios, prior, one, 2)
expected_slow <- exp(-2 / 100) / (exp(-2 / 100) + exp(-2 / 3))
stopifnot(abs(posterior["slow"] - expected_slow) < 1e-12,
          abs(sum(posterior) - 1) < 1e-12,
          identical(scenario_posterior(scenarios, prior), prior))
expect_error(scenario_posterior(scenarios, prior, transform(one, day = 3), 2))
expect_error(scenario_posterior(scenarios, prior, transform(one, shape = 1), 2))
expect_error(scenario_posterior(scenarios, c(fast = -1, slow = 2)))
expect_error(scenario_posterior(scenarios, c(slow = 0.5, fast = 0.5)))
expect_error(normalize_scenario_weights(list(fast = fast,
                                         slow = transform(slow, mass_kg = 101)), prior))

# With just one known scenario, another independent inspection has no economic
# information value. In ties, do not order redundant inspections.
single <- plan_adaptive_inspection(list(fast = fast), c(fast = 1), prices,
                                   0, 1, 2, checks_per_cohort = 10,
                                   eur_per_check = 0)
stopifnot(single$action == "commit",
          abs(single$gross_information_value_eur) < 1e-9)
expect_error(plan_adaptive_inspection(scenarios, prior, prices, 0, 1, 2, 0))
expect_error(plan_adaptive_inspection(scenarios, prior, prices, 0, 1, 2, 6000))
expect_error(plan_adaptive_inspection(scenarios, prior, prices, 0, 2, 2))
expect_error(plan_adaptive_inspection(scenarios, prior, prices[-1, ], 0, 1, 2))
expect_error(sale_after_inspection(cheap, transform(followup, day = 3)))
expect_error(sale_after_inspection(cheap, transform(followup, n_checked = 9)))
expect_error(sale_after_inspection(cheap, transform(followup, true_scale = 100)))

# The synthetic experiment fixes the day-12 plan before any day-16 counts or
# fruit lifetimes are generated. Policy calls receive only predecision data.
original_plan <- plan_adaptive_inspection
original_inspections <- simulate_inspections
original_lifetimes <- simulate_fruit_lifetimes
planned <- FALSE
plan_adaptive_inspection <- function(...) {
  planned <<- TRUE
  original_plan(...)
}
simulate_inspections <- function(truth, days, per_group = 180L) {
  if (any(days > 12)) stopifnot(planned)
  original_inspections(truth, days, per_group)
}
simulate_fruit_lifetimes <- function(truth, mean_fruit_kg = 0.20) {
  stopifnot(planned)
  original_lifetimes(truth, mean_fruit_kg)
}
set.seed(225)
spy_lot <- simulate_adaptive_lot(1)
plan_adaptive_inspection <- original_plan
simulate_inspections <- original_inspections
simulate_fruit_lifetimes <- original_lifetimes
stopifnot(planned, nrow(spy_lot) == 1L)

# All actions are scored on the very same fruit and price paths. Conditional
# return identities catch double-charged inspections or leaked day-16 choices.
records <- run_adaptive_experiment(8, seed = 305)
again <- run_adaptive_experiment(8, seed = 305)
stopifnot(identical(records, again), nrow(records) == 8L,
          all(records$action %in% c("inspect", "commit")),
          all(records$adaptive_day >= 12),
          all(records$always_inspect_day >= 16),
          all(records$adaptive_eur == ifelse(records$action == "inspect",
                                             records$always_inspect_eur,
                                             records$fixed_eur)),
          all((records$net_information_value_eur > 1e-9) ==
                (records$action == "inspect")))
set.seed(421)
summary <- summarize_adaptive_experiment(records, 100)
stopifnot(nrow(summary) == 3L, all(is.finite(summary$mean_gain_eur)),
          all(summary$lower_95_eur <= summary$upper_95_eur),
          all(summary$inspected_fraction == mean(records$action == "inspect")))
expect_error(run_adaptive_experiment(1))
expect_error(summarize_adaptive_experiment(records[-1, ], n_boot = 0))
expect_error(summarize_adaptive_experiment(rbind(records, records[1, ])))
cat("Orange adaptive inspection policy tests passed.\n")
