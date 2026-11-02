# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")
source("R/inspection_removals.R")
source("R/removal_evaluation.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

stock <- data.frame(cohort = c("early", "late", "immature"), mass_kg = c(100, 50, 30),
  initially_sellable = c(TRUE, TRUE, FALSE), shape = c(2, 1, 1), scale = c(10, 100, 1))
prices <- data.frame(cohort = c("early", "late", "early", "late"), day = c(12, 12, 20, 20),
  price_eur_per_kg = c(1, 1, 1, 1.15))
ledger <- data.frame(cohort = "early", day = 6, mass_kg = 95)
empty <- ledger[FALSE, ]
original <- expected_value_grid(stock, prices, 0.001, 12, 2)
stopifnot(identical(value_after_removals(stock, prices, empty, 0.001, 12, 2), original),
          identical(unname(inspection_remaining_mass(stock, ledger, 12)), c(5, 50, 30)))
grid <- value_after_removals(stock, prices, ledger, 0.001, 12, 2)
expected_mass <- 5 * exp(-((c(12, 20) + 2) / 10)^2) + 50 * exp(-(c(12, 20) + 2) / 100)
expected_gross <- 5 * exp(-((c(12, 20) + 2) / 10)^2) +
  50 * exp(-(c(12, 20) + 2) / 100) * c(1, 1.15)
stopifnot(isTRUE(all.equal(grid$expected_sellable_kg, expected_mass)),
          isTRUE(all.equal(grid$expected_net_eur, expected_gross - 55 * 0.001 * c(2, 10))))
# Changed composition can change the optimal date despite identical survival fits.
stopifnot(optimal_batch_sale(stock, prices, 0, 12, 0)$sale_day == 12,
          optimal_sale_after_removals(stock, prices, ledger, 0, 12, 0)$sale_day == 20)
proportional <- data.frame(cohort = c("early", "late"), day = 6, mass_kg = c(25, 12.5))
reduced <- value_after_removals(stock, prices, proportional, 0.001, 12, 2)
stopifnot(isTRUE(all.equal(reduced$expected_net_eur, 0.75 * original$expected_net_eur)),
          reduced$sale_day[which.max(reduced$expected_net_eur)] ==
            original$sale_day[which.max(original$expected_net_eur)])

# Fully depleted strata are removed from both sales and holding cost automatically.
all_early <- transform(ledger, mass_kg = 100)
late_only <- value_after_removals(stock, prices, all_early, 0.001, 12, 2)
manual <- expected_value_grid(stock[2:3, ], subset(prices, cohort == "late"), 0.001, 12, 2)
stopifnot(identical(late_only, manual))
all_eligible <- data.frame(cohort = c("early", "late"), day = 12, mass_kg = c(100, 50))
zero <- value_after_removals(stock, prices, all_eligible, 0.001, 12, 2)
stopifnot(all(zero$expected_sellable_kg == 0), all(zero$expected_net_eur == 0),
          optimal_sale_after_removals(stock, prices, all_eligible, 0.001, 12, 2)$sale_day == 12)
tiny <- transform(stock[1, ], mass_kg = 0.3)
decimal <- data.frame(cohort = "early", day = c(3, 6), mass_kg = c(0.1, 0.2))
stopifnot(inspection_remaining_mass(tiny, decimal, 12) == 0)
expect_error(inspection_remaining_mass(stock, transform(ledger, day = 13), 12))
expect_error(inspection_remaining_mass(stock, transform(ledger, day = 6.5), 12))
expect_error(inspection_remaining_mass(stock, transform(ledger, cohort = "missing"), 12))
expect_error(inspection_remaining_mass(stock, transform(ledger, mass_kg = 100.01), 12))
expect_error(inspection_remaining_mass(stock, transform(ledger, mass_kg = -1), 12))
expect_error(inspection_remaining_mass(stock, transform(ledger, mass_kg = NA_real_), 12))
expect_error(inspection_remaining_mass(stock, rbind(ledger, ledger), 12))
reordered <- stock[3:1, ]
stopifnot(isTRUE(all.equal(value_after_removals(reordered, prices[4:1, ], proportional[2:1, ], 0.001, 12, 2), reduced)))

# The mixture retains its probabilities and weights, and updates both inventories.
other <- transform(stock, shape = c(1.5, 2, 1), scale = c(15, 70, 1))
model <- list(inventories = list(separate = stock, shared = other),
  weights = c(separate = 0.4, shared = 0.6), decision_day = 12)
before <- model
mixed <- ensemble_value_after_removals(model, prices, ledger, 0.001, 2)
other_grid <- value_after_removals(other, prices, ledger, 0.001, 12, 2)
stopifnot(identical(before, model),
          isTRUE(all.equal(mixed$expected_net_eur, 0.4 * grid$expected_net_eur + 0.6 * other_grid$expected_net_eur)),
          identical(ensemble_value_after_removals(model, prices, empty, 0.001, 2),
                    ensemble_value_grid(model, prices, 0.001, 2)),
          optimal_ensemble_sale_after_removals(model, prices, all_eligible, 0.001, 2)$sale_day == 12)

# All decisions precede future generation; fitting receives no true parameters.
original_policy <- fit_removal_policy
original_lifetimes <- removal_study_lifetimes
calls <- 0L
fit_removal_policy <- function(inspections, inventory, prices, removals) {
  calls <<- calls + 1L
  stopifnot(max(inspections$day) <= 12, max(removals$day) <= 12,
            all(inventory$shape == 1), all(inventory$scale == 1), sum(removals$mass_kg) == 288)
  original_policy(inspections, inventory, prices, removals)
}
removal_study_lifetimes <- function(remaining_inventory) {
  stopifnot(calls == 3L)
  lifetimes <- original_lifetimes(remaining_inventory)
  stopifnot(sum(lengths(lifetimes)) == 2810L)
  lifetimes
}
paired <- run_removal_experiment(3, 921, 415)
fit_removal_policy <- original_policy
removal_study_lifetimes <- original_lifetimes
stopifnot(all(abs(paired$remaining_eligible_kg - 562) < 1e-10),
          all(paired$inspection_count == 1440), all(abs(paired$inspection_cost_eur - 28.8) < 1e-10),
          all(paired$fitted_accounted_at_accounted_day_eur >= paired$fitted_accounted_at_naive_day_eur))
other <- run_removal_experiment(3, 921, 416)
fixed <- c("sale_day_naive", "sale_day_accounted", "weight_shared", "fitted_naive_at_naive_day_eur",
  "fitted_accounted_at_naive_day_eur", "fitted_accounted_at_accounted_day_eur")
stopifnot(identical(paired[fixed], other[fixed]), any(paired$realised_accounted_eur != other$realised_accounted_eur))
expect_error(run_removal_experiment(1))

small <- paired[1:2, ]
small$realised_naive_eur <- c(100, 120)
small$realised_accounted_eur <- c(110, 110)
small$realised_immediate_eur <- c(105, 105)
small$true_expected_naive_eur <- c(100, 120)
small$true_expected_accounted_eur <- c(104, 124)
set.seed(22)
summary <- summarize_removal_experiment(small, 100)
stopifnot(summary$realised_return_gain_eur_mean == 0,
          summary$expected_return_gain_eur_mean == 4,
          summary$accounted_minus_immediate_eur_mean == 5,
          summary$accounted_below_naive_fraction == 0.5)
expect_error(summarize_removal_experiment(paired[1, ]))
expect_error(summarize_removal_experiment(rbind(paired, paired[1, ])))
expect_error(summarize_removal_experiment(transform(paired, realised_accounted_eur = Inf)))

# Rebuild the committed report from its paired records, including bootstrap intervals.
saved <- read.csv("results/inspection_removals/records.csv")
settings <- dget("results/inspection_removals/settings.R")
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_removal_experiment(saved, settings$n_boot)
reported <- read.csv("results/inspection_removals/summary.csv")
stopifnot(nrow(saved) == settings$n_lots,
          isTRUE(all.equal(rebuilt, reported, tolerance = 1e-10)))
cat("Orange destructive inspection tests passed.\n")
