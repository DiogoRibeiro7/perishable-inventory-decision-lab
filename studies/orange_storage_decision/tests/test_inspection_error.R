# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/inspection_error.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

stopifnot(isTRUE(all.equal(inspection_label_probability(c(0, 0.5, 1), 0.8, 0.9),
                           c(0.1, 0.45, 0.8))))
stopifnot(identical(inspection_label_probability(c(0, 0.5, 1)), c(0, 0.5, 1)))
expect_error(inspection_label_probability(0.5, 0.5, 0.5))
expect_error(inspection_label_probability(0.5, 1.01, 0.9))
expect_error(inspection_label_probability(0.5, c(0.8, 0.9), 0.9))
expect_error(inspection_label_probability(c(0.2, NA), 0.8, 0.9))

truth <- data.frame(cohort = "eligible", mass_kg = 100,
                    initially_sellable = TRUE, shape = 2, scale = 25)
train <- data.frame(cohort = "eligible", day = c(3, 6, 9, 12), n_checked = 100000L)
# Independently constructed expected label counts. Fit true survival, not labels.
label_p <- 0.8 * exp(-(train$day / 25)^2) + 0.05 * (1 - exp(-(train$day / 25)^2))
train$n_acceptable <- round(train$n_checked * label_p)
corrected <- fit_weibull_by_cohort(train, truth, 0.8, 0.95)
naive <- fit_weibull_by_cohort(train, truth)
stopifnot(abs(corrected$shape - 2) < 0.002, abs(corrected$scale - 25) < 0.02)
future <- c(16, 20, 24)
corrected_error <- mean((weibull_survival(future, corrected$shape, corrected$scale) -
                          exp(-(future / 25)^2))^2)
naive_error <- mean((weibull_survival(future, naive$shape, naive$scale) -
                      exp(-(future / 25)^2))^2)
stopifnot(corrected_error < 1e-6, naive_error > 0.01)
pooled <- fit_pooled_weibull(train, truth, 0.8, 0.95)
stopifnot(abs(pooled$shape - 2) < 0.002, abs(pooled$scale - 25) < 0.02)
stopifnot(identical(fit_weibull_by_cohort(train, truth),
                    fit_weibull_by_cohort(train, truth, 1, 1)))
expect_error(estimate_weibull_binomial(train, sensitivity = 0.4, specificity = 0.5))

# An observed pass fraction can exceed sensitivity due to sampling noise.
# A count likelihood handles this without inverse-correcting counts above n.
extreme <- transform(train, n_checked = 20, n_acceptable = c(20, 15, 10, 8))
edge_fit <- fit_weibull_by_cohort(extreme, truth, 0.8, 0.95)
stopifnot(all(is.finite(c(edge_fit$shape, edge_fit$scale))))

# True positives and false positives are separate binomial draws on the same sample.
clean <- data.frame(cohort = "eligible", day = 1:3, n_checked = 10,
                     n_acceptable = c(0, 4, 10))
uniforms <- matrix(0.5, nrow = 3, ncol = 2)
noisy <- misclassify_inspections(clean, truth, 1, 0.5, uniforms)
stopifnot(identical(noisy$n_acceptable, c(5, 7, 10)))
stopifnot(identical(misclassify_inspections(clean, truth, 1, 1, uniforms), clean))
expect_error(misclassify_inspections(clean, truth, 0.8, 0.9, matrix(0, 3, 2)))
expect_error(misclassify_inspections(clean, truth, 0.8, 0.9, matrix(0.5, 3, 1)))

prices <- data.frame(cohort = "eligible", day = 12:28,
                      price_eur_per_kg = 0.8 + 0.04 * (12:28 - 12))
policy <- fit_inspection_policy(train, truth, prices, 0.8, 0.95)
alternative_placeholders <- transform(truth, shape = 7, scale = 100)
stopifnot(identical(policy,
                    fit_inspection_policy(train, alternative_placeholders, prices, 0.8, 0.95)))
expect_error(fit_inspection_policy(transform(train, day = day + 1), truth, prices))

# Reproduce a bootstrap draw independently: sample reported labels, then refit
# with the same fixed calibration. This catches omission at either stage.
fits <- fit_weibull_by_cohort(train, truth, 0.8, 0.95)
p <- 0.8 * weibull_survival(train$day, fits$shape, fits$scale) +
  0.05 * (1 - weibull_survival(train$day, fits$shape, fits$scale))
set.seed(8123)
resampled <- train
resampled$n_acceptable <- stats::rbinom(nrow(train), train$n_checked, p)
refitted <- with_fitted_survival(truth, fit_weibull_by_cohort(resampled, truth, 0.8, 0.95))
expected <- optimal_batch_sale(refitted, prices, 0.001, 12, 2)
set.seed(8123)
bootstrap <- bootstrap_sale_days(train, truth, prices, 0.001, 12, 2, 1, 0.8, 0.95)
stopifnot(bootstrap$failed == 0, bootstrap$decisions$sale_day == expected$sale_day,
          isTRUE(all.equal(bootstrap$decisions$expected_net_eur, expected$expected_net_eur)))
set.seed(19)
default_bootstrap <- bootstrap_sale_days(train, truth, prices, 0.001, 12, 2, 3)
set.seed(19)
stopifnot(identical(default_bootstrap,
                    bootstrap_sale_days(train, truth, prices, 0.001, 12, 2, 3, 1, 1)))

# No future counts or fruit outcomes are generated until every policy is fixed.
original_fit <- fit_inspection_policy
original_inspections <- simulate_inspections
original_lifetimes <- simulate_fruit_lifetimes
fit_calls <- 0L
fit_inspection_policy <- function(...) {
  fit_calls <<- fit_calls + 1L
  original_fit(...)
}
simulate_inspections <- function(truth, days, per_group = 180L) {
  if (any(days > 12)) stopifnot(fit_calls == 4L)
  original_inspections(truth, days, per_group)
}
simulate_fruit_lifetimes <- function(truth, mean_fruit_kg = 0.20) {
  stopifnot(fit_calls == 4L)
  original_lifetimes(truth, mean_fruit_kg)
}
invisible(run_inspection_error_experiment(2, scenarios = default_inspection_scenarios()[1, ]))
fit_inspection_policy <- original_fit
simulate_inspections <- original_inspections
simulate_fruit_lifetimes <- original_lifetimes

paired <- run_inspection_error_experiment(6, 400, 123, 456)
perfect <- paired[paired$scenario == "perfect", ]
for (metric in c("sale_day_", "realised_", "brier_", "log_loss_")) {
  suffix <- if (metric == "realised_") "_eur" else ""
  stopifnot(identical(perfect[[paste0(metric, "naive", suffix)]],
                      perfect[[paste0(metric, "corrected", suffix)]]))
}
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
settings <- default_inspection_scenarios()
reversed <- run_inspection_error_experiment(6, 400, 123, 456, settings[4:1, ])
stopifnot(identical(sort_records(paired), sort_records(reversed)))
single <- run_inspection_error_experiment(6, 400, 123, 456, settings[3, ])
stopifnot(identical(sort_records(single), sort_records(paired[paired$scenario == settings$scenario[3], ])))
other_outcomes <- run_inspection_error_experiment(6, 400, 123, 999)
dates <- c("sale_day_naive", "sale_day_corrected")
stopifnot(identical(paired[dates], other_outcomes[dates]))
stopifnot(any(paired$realised_immediate_eur != other_outcomes$realised_immediate_eur))
other_labels <- run_inspection_error_experiment(6, 400, 999, 456)
stopifnot(identical(paired$realised_immediate_eur, other_labels$realised_immediate_eur))
stopifnot(identical(perfect, other_labels[other_labels$scenario == "perfect", ]))
stopifnot(any(paired$brier_naive != other_labels$brier_naive))
expect_error(run_inspection_error_experiment(1))

small <- perfect[1:2, ]
small$realised_corrected_eur <- c(10, 30)
small$realised_naive_eur <- c(20, 20)
small$realised_immediate_eur <- c(15, 20)
small$brier_naive <- c(0.2, 0.3)
small$brier_corrected <- c(0.1, 0.2)
set.seed(17)
summary <- summarize_inspection_error(small, 100)
stopifnot(summary$corrected_minus_naive_eur_mean == 0,
          summary$corrected_minus_immediate_eur_mean == 2.5,
          isTRUE(all.equal(summary$brier_improvement_mean, 0.1)),
          summary$corrected_below_immediate_fraction == 0.5)
expect_error(summarize_inspection_error(paired[-1, ]))
expect_error(summarize_inspection_error(rbind(paired, paired[1, ])))
expect_error(summarize_inspection_error(transform(paired, brier_naive = Inf)))

# Saved evidence can be reconstructed from the paired records and declared seed.
saved <- utils::read.csv("results/inspection_error/records.csv")
settings <- dget("results/inspection_error/settings.R")
stopifnot(nrow(saved) == settings$n_lots * nrow(settings$scenarios))
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_inspection_error(saved, settings$n_boot)
committed <- utils::read.csv("results/inspection_error/summary.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange storage inspection error tests passed.\n")
