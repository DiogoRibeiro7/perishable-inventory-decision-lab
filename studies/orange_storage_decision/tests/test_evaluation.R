# Dependency-free prospective evaluation tests, run from project directory:
# Rscript tests/test_evaluation.R

source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")

expect_error <- function(expression) {
  observed <- tryCatch({
    force(expression)
    FALSE
  }, error = function(error) TRUE)
  stopifnot(observed)
}

truth <- data.frame(
  cohort = c("advanced", "intermediate", "initially_immature"),
  mass_kg = c(300, 550, 150),
  initially_sellable = c(TRUE, TRUE, FALSE),
  shape = c(2.1, 1.7, 1),
  scale = c(16, 40, 1),
  stringsAsFactors = FALSE
)

# Deterministic counts remove sampling noise from the model comparison.
make_counts <- function(days, sample_size) {
  inspections <- expand.grid(
    cohort = c("advanced", "intermediate"), day = days,
    KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
  )
  inspections$n_checked <- as.integer(sample_size)
  position <- match(inspections$cohort, truth$cohort)
  inspections$n_acceptable <- as.integer(round(
    sample_size * weibull_survival(
      inspections$day, truth$shape[position], truth$scale[position]
    )
  ))
  inspections
}
train <- make_counts(c(3, 6, 9, 12), 2500L)
holdout <- make_counts(c(16, 20, 24), 2500L)

# The weighted pooled baseline respects mass fractions, not oversampling.
weights <- inventory_sampling_weights(train, truth)
for (day in unique(train$day)) {
  rows <- train$day == day
  stopifnot(isTRUE(all.equal(
    sum(train$n_checked[rows] * weights[rows]),
    sum(train$n_checked[rows]), tolerance = 1e-10
  )))
}
expect_error(inventory_sampling_weights(train[1, , drop = FALSE],
                                        transform(truth, mass_kg = -1)))

stratified <- with_fitted_survival(truth, fit_weibull_by_cohort(train, truth))
pooled_fit <- fit_pooled_weibull(train, truth)
stopifnot(is.finite(pooled_fit$objective), pooled_fit$shape > 0,
          pooled_fit$scale > 0)
pooled <- with_pooled_survival(truth, pooled_fit)
stopifnot(length(unique(pooled$shape[pooled$initially_sellable])) == 1L)
stopifnot(length(unique(pooled$scale[pooled$initially_sellable])) == 1L)
expect_error(with_pooled_survival(truth, list(shape = 0, scale = 2)))

stratified_score <- score_future_inspections(holdout, stratified, 12L)
pooled_score <- score_future_inspections(holdout, pooled, 12L)
stopifnot(stratified_score$brier >= 0, stratified_score$brier <= 1,
          stratified_score$log_loss > 0,
          stratified_score$brier < pooled_score$brier,
          stratified_score$log_loss < pooled_score$log_loss)
expect_error(score_future_inspections(train, stratified, 12L))
expect_error(score_future_inspections(holdout, stratified, 16L))

# Scoring an already fitted model needs no new curve-identification data.
# Compare aggregate scores with explicitly expanded individual fruit outcomes,
# using unequal inspection sizes and independently specified inventory shares.
score_inventory <- truth
score_inventory$mass_kg[1:2] <- c(100, 300)
score_inventory$shape[1:2] <- 1
score_inventory$scale[1:2] <- -20 / log(c(0.2, 0.7))
single_day <- data.frame(
  cohort = c("advanced", "intermediate"), day = c(20L, 20L),
  n_checked = c(2L, 8L), n_acceptable = c(1L, 5L),
  stringsAsFactors = FALSE
)
individual_y <- c(1, 0, rep(1, 5), rep(0, 3))
individual_p <- c(rep(0.2, 2), rep(0.7, 8))
individual_weight <- c(rep(0.25 / 2, 2), rep(0.75 / 8, 8))
single_score <- score_future_inspections(single_day, score_inventory, 12L)
stopifnot(isTRUE(all.equal(
  single_score$brier,
  sum(individual_weight * (individual_y - individual_p)^2)
)))
stopifnot(isTRUE(all.equal(
  single_score$log_loss,
  -sum(individual_weight * (individual_y * log(individual_p) +
                            (1 - individual_y) * log1p(-individual_p)))
)))

for (all_pass in c(FALSE, TRUE)) {
  boundary <- single_day
  boundary$n_acceptable <- if (all_pass) boundary$n_checked else c(0L, 0L)
  boundary_score <- score_future_inspections(boundary, score_inventory, 12L)
  p <- c(0.2, 0.7)
  expected_brier <- sum(c(0.25, 0.75) * (as.numeric(all_pass) - p)^2)
  expected_log_loss <- -sum(c(0.25, 0.75) *
                             if (all_pass) log(p) else log1p(-p))
  stopifnot(isTRUE(all.equal(boundary_score$brier, expected_brier)))
  stopifnot(isTRUE(all.equal(boundary_score$log_loss, expected_log_loss)))
}
opposite <- single_day
opposite$n_acceptable <- c(0L, 8L)
opposite_score <- score_future_inspections(opposite, score_inventory, 12L)
stopifnot(isTRUE(all.equal(opposite_score$brier, 0.25 * 0.2^2 + 0.75 * 0.3^2)))
stopifnot(isTRUE(all.equal(opposite_score$log_loss,
                          -0.25 * log(0.8) - 0.75 * log(0.7))))

# Row order and proportional oversampling of one stratum cannot change the
# inventory-standardised score on this single inspection day.
oversampled <- single_day
oversampled$n_checked[1] <- 20L
oversampled$n_acceptable[1] <- 10L
stopifnot(isTRUE(all.equal(single_score,
  score_future_inspections(oversampled[2:1, ], score_inventory, 12L))))
unequal_weight <- inventory_sampling_weights(single_day, score_inventory)
stopifnot(isTRUE(all.equal(
  unequal_weight * single_day$n_checked / sum(single_day$n_checked),
  c(0.25, 0.75)
)))

# Releasing scoring constraints must not release fitting or leakage checks.
expect_error(fit_weibull_by_cohort(single_day, score_inventory))
expect_error(fit_pooled_weibull(single_day, score_inventory))
for (all_pass in c(FALSE, TRUE)) {
  boundary_train <- train
  boundary_train$n_acceptable <- if (all_pass) boundary_train$n_checked else
    rep(0L, nrow(boundary_train))
  expect_error(fit_weibull_by_cohort(boundary_train, truth))
  expect_error(fit_pooled_weibull(boundary_train, truth))
}
expect_error(score_future_inspections(single_day, score_inventory, 20L))
expect_error(score_future_inspections(single_day, score_inventory, 21L))
expect_error(score_future_inspections(single_day[1, , drop = FALSE],
                                      score_inventory, 12L))
expect_error(score_future_inspections(rbind(single_day, single_day[1, ]),
                                      score_inventory, 12L))
for (bad_count in c(-1, 3, 0.5, NA_real_, Inf)) {
  broken_holdout <- single_day
  broken_holdout$n_acceptable[1] <- bad_count
  expect_error(score_future_inspections(broken_holdout, score_inventory, 12L))
}

# Weighting needs all inventory strata on each day, not just somewhere in the
# table. Otherwise a missing stratum silently changes the target population.
incomplete <- train[-1, ]
validate_inspections(incomplete, truth)  # Still enough observations to fit each curve.
expect_error(inventory_sampling_weights(incomplete, truth))
expect_error(fit_pooled_weibull(incomplete, truth))
incomplete$day <- incomplete$day + 20L
expect_error(score_future_inspections(incomplete, stratified, 12L))
expect_error(inventory_sampling_weights(train[FALSE, ], truth))
expect_error(inventory_sampling_weights(rbind(train, train[1, ]), truth))
for (field in c("day", "n_checked")) {
  for (bad_value in c(0, -1, 0.5, NA_real_, Inf)) {
    malformed <- train
    malformed[[field]][1] <- bad_value
    expect_error(inventory_sampling_weights(malformed, truth))
  }
}

# Reuse one fixed set of fruit-level potential outcomes for all policies.
set.seed(123L)
lifetimes <- simulate_fruit_lifetimes(truth)
prices <- simulate_price_scenario(decision_day = 12L, horizon = 28L)
sale_value <- function(day) {
  realised_sale_value(day, truth, prices, lifetimes, 0.001, 12L, 2L)
}
stopifnot(identical(sale_value(12L), sale_value(12L)))
stopifnot(is.finite(sale_value(20L)))
expect_error(sale_value(29L))
expect_error(realised_sale_value(12L, truth, prices, list(), 0.001, 12L))

# Every lot is independent; runs with the same seed must be bit-for-bit stable.
experiment_a <- run_policy_experiment(n_lots = 6L, seed = 400L)
experiment_b <- run_policy_experiment(n_lots = 6L, seed = 400L)
stopifnot(identical(experiment_a, experiment_b))
stopifnot(nrow(experiment_a) == 6L)
stopifnot(all(is.finite(as.matrix(experiment_a))))
stopifnot(all(experiment_a$sale_day_stratified >= 12L))
stopifnot(all(experiment_a$sale_day_pooled <= 28L))
stopifnot(all(experiment_a$brier_stratified >= 0))
expect_error(run_policy_experiment(n_lots = 1L))

set.seed(20L)
interval <- paired_lot_interval(c(-1, 0, 1, 2), n_boot = 200L)
stopifnot(identical(names(interval), c("mean", "lower_95", "upper_95")))
stopifnot(interval[["mean"]] == 0.5)
stopifnot(interval[["lower_95"]] <= interval[["mean"]])
stopifnot(interval[["upper_95"]] >= interval[["mean"]])
expect_error(paired_lot_interval(1))
expect_error(paired_lot_interval(c(1, NA_real_)))

# Likelihood helper refuses broken data and silently omitted counts.
expect_error(estimate_weibull_binomial(train, rep(0, nrow(train))))
broken <- train
broken$n_acceptable[1] <- -1L
expect_error(estimate_weibull_binomial(broken))

cat("Orange storage out-of-time evaluation tests passed.\n")
