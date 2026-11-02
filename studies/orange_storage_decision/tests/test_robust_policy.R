# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")
source("R/robust_policy.R")
source("R/robust_evaluation.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

# Hand-worked expected returns: optimistic (100, 140, 150), adverse (100, 90, 0).
# Scenario regrets are (50, 10, 0) and (0, 10, 100), so day 2 is the compromise.
# Forecast optimisation chooses day 3; maximising worst profit chooses day 1.
inventory <- data.frame(cohort = "eligible", mass_kg = 100,
                        initially_sellable = TRUE, shape = 1, scale = 10)
price_grid <- function(values) {
  data.frame(cohort = "eligible", day = 1:3,
              price_eur_per_kg = values / (100 * exp(-(1:3) / 10)))
}
paths <- list(optimistic = price_grid(c(100, 140, 150)),
              adverse = price_grid(c(100, 90, 0)))
chosen <- minimax_regret_sale(inventory, paths, 0, 1)
stopifnot(chosen$decision$sale_day == 2,
          isTRUE(all.equal(chosen$grid$worst_regret_eur, c(50, 10, 100))))
stopifnot(isTRUE(all.equal(chosen$scenario_values$regret_eur,
                           c(50, 10, 0, 0, 10, 100))))
stopifnot(optimal_batch_sale(inventory, paths$optimistic, 0, 1)$sale_day == 3)
stopifnot(chosen$grid$sale_day[which.max(chosen$grid$worst_expected_net_eur)] == 1)

# One scenario reduces to ordinary expected-value optimisation. Current-only
# grids work, shuffled days/scenarios do not change the decision, ties go early.
single <- minimax_regret_sale(inventory, paths[1], 0.1, 1, 2)
ordinary <- optimal_batch_sale(inventory, paths[[1]], 0.1, 1, 2)
stopifnot(single$decision$sale_day == ordinary$sale_day)
stopifnot(isTRUE(all.equal(single$grid$worst_expected_net_eur,
                           c(100, 140, 150) * exp(-0.2) - 10 * c(2, 3, 4))))
shuffled <- lapply(paths[2:1], function(x) x[3:1, ])
stopifnot(identical(minimax_regret_sale(inventory, shuffled, 0, 1)$grid, chosen$grid))
today <- lapply(paths, function(x) x[1, ])
stopifnot(minimax_regret_sale(inventory, today, 0, 1)$decision$sale_day == 1)
zero <- price_grid(c(0, 0, 0))
stopifnot(minimax_regret_sale(inventory, list(zero = zero), 0, 1)$decision$sale_day == 1)
expect_error(minimax_regret_sale(inventory, unname(paths), 0, 1))
expect_error(minimax_regret_sale(inventory, setNames(paths, c("x", "x")), 0, 1))
expect_error(minimax_regret_sale(inventory, list(), 0, 1))
bad <- paths
bad[[2]] <- bad[[2]][-2, ]
expect_error(minimax_regret_sale(inventory, bad, 0, 1))
bad <- paths
bad[[2]]$price_eur_per_kg[1] <- 10
expect_error(minimax_regret_sale(inventory, bad, 0, 1))
expect_error(minimax_regret_sale(inventory, paths, -1, 1))
expect_error(price_mean_scenarios(paths[[1]], inventory, 1, c(0.6, 0.6)))
expect_error(price_mean_scenarios(paths[[1]], inventory, 1, c(0, 1)))

# Policy scenarios are conditional means, with no sampled future information.
set.seed(18)
state <- .Random.seed
means <- price_mean_scenarios(paths[[1]], inventory, 1, c(0.6, 1))
invisible(minimax_regret_sale(inventory, means, 0, 1))
stopifnot(identical(state, .Random.seed))
stopifnot(isTRUE(all.equal(means[[1]]$price_eur_per_kg /
                           paths[[1]]$price_eur_per_kg, c(1, sqrt(0.6), 0.6))))

# Verify the policy is invoked before held-out inspections/fruit outcomes.
original_inspections <- simulate_inspections
original_lifetimes <- simulate_fruit_lifetimes
called <- FALSE
simulate_inspections <- function(truth, days, per_group = 180L) {
  if (any(days > 12)) stopifnot(called)
  original_inspections(truth, days, per_group)
}
simulate_fruit_lifetimes <- function(truth, mean_fruit_kg = 0.20) {
  stopifnot(called)
  original_lifetimes(truth, mean_fruit_kg)
}
set.seed(400)
prepared <- simulate_policy_lot(1, additional_policy = function(cohorts, prices, cost, day, lag) {
  called <<- TRUE
  optimal_batch_sale(cohorts, prices, cost, day, lag)$sale_day
})
simulate_inspections <- original_inspections
simulate_fruit_lifetimes <- original_lifetimes
stopifnot(called, prepared$additional_day == prepared$stratified_day)
expect_error(simulate_policy_lot(1, additional_policy = 12))
expect_error(simulate_policy_lot(1, additional_policy = function(...) 100))

# Adding the policy preserves the baseline's lots, fruit and paired price RNG.
paired <- run_robust_policy_experiment(8, 400, 123)
baseline <- run_price_sensitivity(8, 400, 123)
common <- c("scenario", "lot_id", "sale_day_stratified", "sale_day_pooled",
             "realised_stratified_eur", "realised_pooled_eur", "realised_immediate_eur")
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
shared <- paired[paired$scenario %in% baseline$scenario, common]
stopifnot(identical(sort_records(shared), sort_records(baseline[common])))
stopifnot(any(paired$sale_day_robust != paired$sale_day_stratified))
other_prices <- run_robust_policy_experiment(8, 400, 456)
fixed <- c("lot_id", "sale_day_stratified", "sale_day_pooled", "sale_day_robust",
            "realised_immediate_eur")
stopifnot(identical(paired[fixed], other_prices[fixed]))
stopifnot(any(paired$realised_robust_eur != other_prices$realised_robust_eur))
settings <- robust_evaluation_scenarios()
reversed <- run_robust_policy_experiment(8, 400, 123, scenarios = settings[6:1, ])
stopifnot(identical(sort_records(paired), sort_records(reversed)))
subset <- run_robust_policy_experiment(8, 400, 123, scenarios = settings[5, ])
stopifnot(identical(sort_records(subset),
                    sort_records(paired[paired$scenario == settings$scenario[5], ])))
point_only <- run_robust_policy_experiment(8, 400, 123, decision_ratios = 1)
stopifnot(all(point_only$sale_day_robust == point_only$sale_day_stratified))
stopifnot(all(point_only$realised_robust_eur == point_only$realised_stratified_eur))
stopifnot(identical(paired[common], point_only[common]))
expect_error(run_robust_policy_experiment(1))

# Hand-worked profit differences and downside summaries, including ties.
small <- paired[paired$scenario == "perfect_forecast", ][1:2, ]
small$realised_robust_eur <- c(10, 30)
small$realised_stratified_eur <- c(20, 20)
small$realised_pooled_eur <- c(15, 25)
small$realised_immediate_eur <- c(15, 20)
set.seed(12)
summary <- summarize_robust_policy(small, 100)
stopifnot(summary$robust_minus_stratified_mean_eur == 0,
          summary$robust_minus_immediate_mean_eur == 2.5,
          summary$robust_below_immediate_fraction == 0.5,
          summary$stratified_below_immediate_fraction == 0,
          isTRUE(all.equal(summary$robust_minus_immediate_p10_eur, -3.5)))
expect_error(summarize_robust_policy(paired[-1, ]))
expect_error(summarize_robust_policy(rbind(paired, paired[1, ])))
expect_error(summarize_robust_policy(transform(paired, realised_robust_eur = Inf)))
bad <- paired
bad$sale_day_robust[1] <- 28
bad$sale_day_robust[2] <- 12
expect_error(summarize_robust_policy(bad))

# Committed measurements reproduce every reported summary from recorded seeds.
directory <- "results/robust_policy"
saved <- utils::read.csv(file.path(directory, "records.csv"), stringsAsFactors = FALSE)
saved_settings <- dget(file.path(directory, "settings.R"))
stopifnot(nrow(saved) == saved_settings$n_lots * nrow(saved_settings$scenarios))
stopifnot(identical(saved_settings$decision_ratios, c(0.6, 0.8, 1)))
set.seed(saved_settings$bootstrap_seed)
rebuilt <- summarize_robust_policy(saved, saved_settings$n_boot)
committed <- utils::read.csv(file.path(directory, "summary.csv"), stringsAsFactors = FALSE)
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange storage minimax-regret policy tests passed.\n")
