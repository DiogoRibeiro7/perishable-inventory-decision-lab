# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}
w <- aic_shape_weights(c(10, 11), c(4, 3))
stopifnot(identical(w$aic, c(28, 28)), identical(w$weight, c(0.5, 0.5)))
w <- aic_shape_weights(c(10, 10), c(4, 3))
stopifnot(isTRUE(all.equal(w$weight, c(exp(-1), 1) / (1 + exp(-1)))))
stopifnot(identical(aic_shape_weights(c(1e6, 0), c(2, 2))$weight, c(0, 1)))
expect_error(aic_shape_weights(c(NA, 1), c(2, 3)))
expect_error(aic_shape_weights(c(1, 2), c(2, 0)))
expect_error(aic_shape_weights(c(1, 2), c(2, 2.5)))

# Hand-built mixture: average probabilities and values, not parameters or dates.
stock <- data.frame(cohort = c("eligible", "immature"), mass_kg = c(100, 30),
  initially_sellable = c(TRUE, FALSE), shape = c(2, 1), scale = c(15, 1))
other <- transform(stock, shape = c(1, 1), scale = c(40, 1))
model <- list(inventories = list(separate = stock, shared = other),
  weights = c(separate = 0.25, shared = 0.75), decision_day = 12)
p <- predict_shape_ensemble(model, c("eligible", "eligible"), c(20, 0))
stopifnot(isTRUE(all.equal(unname(p), c(0.25 * exp(-(20 / 15)^2) + 0.75 * exp(-20 / 40), 1))))
averaged_parameters <- exp(-(20 / (0.25 * 15 + 0.75 * 40))^(0.25 * 2 + 0.75))
stopifnot(abs(p[1] - averaged_parameters) > 0.01)
prices <- data.frame(cohort = "eligible", day = 12:28, price_eur_per_kg = 0.8 + 0.04 * (12:28 - 12))
grid <- ensemble_value_grid(model, prices, 0.001, 2)
expected_mass <- 100 * (0.25 * exp(-((prices$day + 2) / 15)^2) +
                         0.75 * exp(-(prices$day + 2) / 40))
expected_net <- expected_mass * prices$price_eur_per_kg - 0.001 * 100 * (prices$day - 12 + 2)
stopifnot(isTRUE(all.equal(grid$expected_sellable_kg, expected_mass)),
          isTRUE(all.equal(grid$expected_net_eur, expected_net)),
          optimal_ensemble_sale(model, prices, 0.001, 2)$sale_day == prices$day[which.max(expected_net)])
stopifnot(optimal_ensemble_sale(model, transform(prices, price_eur_per_kg = 0), 0, 2)$sale_day == 12)
bad <- model
bad$weights <- c(separate = 0.8, shared = 0.8)
expect_error(predict_shape_ensemble(bad, "eligible", 20))
bad <- model
bad$inventories$shared$mass_kg[1] <- 90
expect_error(ensemble_value_grid(bad, prices, 0.001, 2))
expect_error(predict_shape_ensemble(model, "immature", 20))
expect_error(predict_shape_ensemble(model, rep("eligible", 2), 20))

# Direct probability scores agree with the fruit-level formula and existing scorer.
holdout <- data.frame(cohort = "eligible", day = 20, n_checked = 10, n_acceptable = 3)
scores <- score_future_probabilities(holdout, stock, 0.4, 12)
stopifnot(isTRUE(all.equal(scores$brier, (3 * 0.6^2 + 7 * 0.4^2) / 10)),
          isTRUE(all.equal(scores$log_loss, -(3 * log(0.4) + 7 * log(0.6)) / 10)))
stopifnot(identical(score_future_inspections(holdout, stock, 12),
  score_future_probabilities(holdout, stock, exp(-(20 / 15)^2), 12)))
expect_error(score_future_probabilities(holdout, stock, c(0.4, 0.5), 12))
expect_error(score_future_probabilities(holdout, stock, 1.1, 12))
expect_error(score_future_probabilities(holdout, stock, NA_real_, 12))
expect_error(score_future_probabilities(holdout, stock, 0.4, 20))

train <- data.frame(cohort = "eligible", day = c(3, 6, 9, 12), n_checked = 500,
  n_acceptable = round(500 * exp(-(c(3, 6, 9, 12) / 25)^2)))
one <- fit_shape_ensemble(train, stock, 12)
stopifnot(identical(unname(one$weights), c(0.5, 0.5)),
          identical(one$comparison$parameters, c(2, 2)))
stopifnot(isTRUE(all.equal(predict_shape_ensemble(one, "eligible", 20),
  weibull_survival(20, one$inventories$separate$shape[1], one$inventories$separate$scale[1]))))
expect_error(fit_shape_ensemble(transform(train, day = day + 1), stock, 12))
expect_error(assemble_shape_ensemble(list(separate = data.frame(), shared = data.frame()), stock, 12))

# Flat-likelihood regression: a scale-bound solution must not defeat a feasible
# shared-shape point when calculating AIC for the more flexible component.
flat <- expand.grid(cohort = c("advanced", "intermediate"), day = c(3, 6, 9, 12),
                      KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
flat$n_checked <- 180
flat$n_acceptable <- c(153, 159, 148, 156, 123, 168, 82, 153)
flat_stock <- data.frame(cohort = c("advanced", "intermediate"), mass_kg = c(400, 450),
  initially_sellable = TRUE, shape = 1, scale = 1)
refined <- fit_shape_ensemble(flat, flat_stock, 12, 0.9, 0.9)
stopifnot(refined$comparison$negative_log_likelihood[1] <=
            refined$comparison$negative_log_likelihood[2] + 2e-8,
          refined$weights["shared"] <= plogis(1) + 1e-8)
for (group in flat_stock$cohort) {
  separate_loss <- refined$fits$separate$negative_log_likelihood[refined$fits$separate$cohort == group]
  shared_loss <- refined$fits$shared$negative_log_likelihood[refined$fits$shared$cohort == group]
  stopifnot(separate_loss <= shared_loss + 1e-8)
}

# Study builder uses exactly the same past fits/likelihoods as the public API.
set.seed(34)
truth <- simulate_true_inventory()
public <- transform(truth, shape = 1, scale = 1)
train <- shape_study_inspections(truth, c(3, 6, 9, 12), 180, runif(8), 0.9, 0.9)
prices <- simulate_price_scenario()
policies <- lapply(c("separate", "shared"), function(name) fit_ensemble_shape_policy(train, public, prices, name))
names(policies) <- c("separate", "shared")
built <- shape_ensemble_policy(train, public, prices, policies)
direct <- fit_shape_ensemble(train, public, 12, 0.9, 0.9)
stopifnot(built$diagnostics["weight_shared"] == direct$weights["shared"],
          built$sale_day == optimal_ensemble_sale(direct, prices, 0.001, 2)$sale_day)
hidden <- fit_shape_ensemble(train, transform(public, shape = 7, scale = 90), 12, 0.9, 0.9)
stopifnot(identical(direct$comparison, hidden$comparison),
          identical(predict_shape_ensemble(direct, train$cohort, train$day),
                    predict_shape_ensemble(hidden, train$cohort, train$day)),
          identical(optimal_ensemble_sale(direct, prices, 0.001, 2),
                    optimal_ensemble_sale(hidden, prices, 0.001, 2)))

# All ensemble dates/weights are fixed before any future outcome uniforms exist.
original_builder <- shape_ensemble_policy
original_outcomes <- shape_study_outcome_uniforms
calls <- 0L
shape_ensemble_policy <- function(inspections, inventory, prices, policies) {
  calls <<- calls + 1L
  stopifnot(max(inspections$day) <= 12, all(inventory$shape == 1), all(inventory$scale == 1))
  original_builder(inspections, inventory, prices, policies)
}
shape_study_outcome_uniforms <- function(...) {
  stopifnot(calls == 6L)
  original_outcomes(...)
}
invisible(run_shape_ensemble_experiment(2, 461, 762))
shape_ensemble_policy <- original_builder
shape_study_outcome_uniforms <- original_outcomes

paired <- run_shape_ensemble_experiment(5, 461, 762)
baseline <- run_shared_shape_experiment(5, 461, 762, policy_fitter = fit_ensemble_shape_policy)
stopifnot(identical(paired[names(baseline)], baseline))
other <- run_shape_ensemble_experiment(5, 461, 999)
fixed <- c("sale_day_ensemble", "ensemble_weight_shared", "ensemble_nll_separate", "ensemble_nll_shared")
stopifnot(identical(paired[fixed], other[fixed]), any(paired$brier_ensemble != other$brier_ensemble))
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
scenarios <- default_shape_scenarios()
reversed <- run_shape_ensemble_experiment(5, 461, 762, scenarios[3:1, ])
stopifnot(identical(sort_records(paired), sort_records(reversed)))
single <- run_shape_ensemble_experiment(5, 461, 762, scenarios[3, ])
stopifnot(identical(sort_records(single), sort_records(subset(paired, scenario == "different_shapes"))))
expect_error(run_shared_shape_experiment(2, additional_policy = 1))
expect_error(run_shared_shape_experiment(2, policy_fitter = 1))
expect_error(run_shared_shape_experiment(2, additional_policy = function(...) list(sale_day = 29, predict = identity)))

small <- subset(paired, scenario == "common_shape")[1:2, ]
small$realised_ensemble_eur <- c(10, 30)
small$realised_shared_eur <- c(20, 20)
small$realised_immediate_eur <- c(15, 20)
small$brier_shared <- c(0.2, 0.3)
small$brier_ensemble <- c(0.1, 0.2)
set.seed(11)
summary <- summarize_shape_ensemble(small, 100)
stopifnot(summary$ensemble_minus_shared_eur_mean == 0,
          summary$ensemble_minus_immediate_eur_mean == 2.5,
          isTRUE(all.equal(summary$brier_improvement_vs_shared_mean, 0.1)),
          summary$ensemble_below_immediate_fraction == 0.5)
expect_error(summarize_shape_ensemble(paired[-1, ]))
expect_error(summarize_shape_ensemble(transform(paired, ensemble_weight_shared = 1.1)))
expect_error(summarize_shape_ensemble(transform(paired, brier_ensemble = Inf)))

# Committed evidence reconstructs its declared bootstrap summary, and respects
# the nested component likelihoods used to calculate the saved AIC weights.
saved <- utils::read.csv("results/shape_ensemble/records.csv")
settings <- dget("results/shape_ensemble/settings.R")
stopifnot(nrow(saved) == settings$n_lots * nrow(settings$scenarios),
          all(saved$ensemble_nll_separate <= saved$ensemble_nll_shared + 2e-8))
expected_weights <- plogis(saved$ensemble_nll_separate - saved$ensemble_nll_shared + 1)
stopifnot(isTRUE(all.equal(saved$ensemble_weight_shared, expected_weights, tolerance = 1e-10)))
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_shape_ensemble(saved, settings$n_boot)
committed <- utils::read.csv("results/shape_ensemble/summary.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))
cat("Orange shape ensemble tests passed.\n")
