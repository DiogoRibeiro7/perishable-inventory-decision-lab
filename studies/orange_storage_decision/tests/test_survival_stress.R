# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")
source("R/robust_policy.R")
source("R/robust_evaluation.R")
source("R/survival_stress.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

# H(t)=(t/20)^2; after day 10 multiply the incremental hazard by two.
days <- c(0, 5, 10, 20)
actual <- changed_hazard_survival(days, 2, 20, 10, 2)
stopifnot(isTRUE(all.equal(actual, exp(-c(0, 0.0625, 0.25, 1.75)))))
stopifnot(identical(changed_hazard_survival(days, 2, 20, 10, 1),
                    weibull_survival(days, 2, 20)))
stopifnot(identical(actual[1:3], weibull_survival(days[1:3], 2, 20)))
stopifnot(isTRUE(all.equal(changed_hazard_survival(days, 2, 20, 0, 2),
                           exp(-2 * (days / 20)^2))))
stopifnot(changed_hazard_survival(1e300, 10, 1e-100, 10, 2) == 0)
expect_error(changed_hazard_survival(days, 0, 20, 10, 2))
expect_error(changed_hazard_survival(days, 2, 20, 10, 0))
expect_error(changed_hazard_survival(days, 2, 20, -1, 2))

truth <- data.frame(cohort = "eligible", mass_kg = 100,
                    initially_sellable = TRUE, shape = 2, scale = 20)
times <- list(eligible = c(0, 5, 10, 20, 30))
set.seed(17)
state <- .Random.seed
stressed <- stress_fruit_lifetimes(times, truth, 10, 2)
stopifnot(identical(stressed$eligible[1:3], times$eligible[1:3]))
stopifnot(isTRUE(all.equal(stressed$eligible[4:5], sqrt(c(250, 500)))))
stopifnot(identical(stress_fruit_lifetimes(times, truth, 10, 1), times))
stopifnot(all(stress_fruit_lifetimes(times, truth, 10, 0.5)$eligible >= times$eligible))
stopifnot(isTRUE(all.equal(
  changed_hazard_survival(stressed$eligible, 2, 20, 10, 2),
  weibull_survival(times$eligible, 2, 20)
)))
stopifnot(identical(state, .Random.seed))
expect_error(stress_fruit_lifetimes(list(wrong = 20), truth, 10, 2))
expect_error(stress_fruit_lifetimes(list(eligible = Inf), truth, 10, 2))
expect_error(stress_fruit_lifetimes(times, truth, 10, 0))

# The transformed empirical survival distribution matches the analytic curve.
# A deterministic quantile grid avoids a statistical false-failure probability.
n <- 10001L
quantiles <- list(eligible = stats::qweibull((seq_len(n) - 0.5) / n, 2, 20))
warped <- stress_fruit_lifetimes(quantiles, truth, 12, 1.5)$eligible
future <- c(14, 16, 20, 24)
empirical <- vapply(future, function(day) mean(warped > day), numeric(1))
stopifnot(max(abs(empirical - changed_hazard_survival(future, 2, 20, 12, 1.5))) < 1 / n)

# Counts use the same uniforms with correct binomial marginal probabilities.
uniforms <- c(0.2, 0.5, 0.8)
inspections <- stress_inspections(truth, c(10, 16, 20), 12, 2, uniforms, 100)
expected_p <- exp(-c(0.25, 0.36 + 2 * (0.64 - 0.36), 0.36 + 2 * (1 - 0.36)))
stopifnot(identical(inspections$n_acceptable, stats::qbinom(uniforms, 100, expected_p)))
slow <- stress_inspections(truth, c(10, 16, 20), 12, 0.5, uniforms, 100)
stopifnot(slow$n_acceptable[1] == inspections$n_acceptable[1],
          all(slow$n_acceptable >= inspections$n_acceptable))
expect_error(stress_inspections(truth, 16, 12, 2, 0))
expect_error(stress_inspections(truth, c(16, 16), 12, 2, c(0.2, 0.8)))
expect_error(validate_survival_scenarios(rbind(default_survival_scenarios(),
                                              default_survival_scenarios()[1, ])))

# Hand-worked individual-fruit Brier and signed calibration error: p=.2, y/n=.4.
fitted <- transform(truth, shape = 1, scale = -20 / log(0.2))
holdout <- data.frame(cohort = "eligible", day = 20, n_checked = 5, n_acceptable = 2)
score <- score_stress_inspections(holdout, fitted, 12)
stopifnot(isTRUE(all.equal(score$bias, -0.2)), isTRUE(all.equal(score$brier, 0.28)))
expect_error(score_stress_inspections(holdout, fitted, 20))

# Unchanged-hazard economic outcomes exactly match the earlier policy generator.
paired <- run_survival_stress(8, 400, 123)
baseline <- run_robust_policy_experiment(8, 400, 456)
original <- baseline[baseline$scenario == "perfect_forecast", ]
unchanged <- paired[paired$scenario == "unchanged", ]
economic <- c("lot_id", "sale_day_stratified", "sale_day_pooled", "sale_day_robust",
               "realised_stratified_eur", "realised_pooled_eur", "realised_robust_eur",
               "realised_immediate_eur")
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
rownames(original) <- rownames(unchanged) <- NULL
stopifnot(identical(original[economic], unchanged[economic]))
stopifnot(!any(grepl("oracle", names(paired))))
for (id in unique(paired$lot_id)) {
  part <- paired[paired$lot_id == id, ]
  stopifnot(nrow(unique(part[c("sale_day_stratified", "sale_day_pooled", "sale_day_robust")])) == 1)
  part <- part[order(part$hazard_multiplier), ]
  for (column in c("realised_stratified_eur", "realised_pooled_eur",
                    "realised_robust_eur", "realised_immediate_eur")) {
    stopifnot(all(diff(part[[column]]) <= 0))
  }
}
# Immediate sale is exposed during its two-day delivery lag, too.
fast <- paired[paired$scenario == "double_hazard", ]
stopifnot(any(fast$realised_immediate_eur < unchanged$realised_immediate_eur))
other_counts <- run_survival_stress(8, 400, 456)
stopifnot(identical(paired[economic], other_counts[economic]))
stopifnot(any(paired$brier_stratified != other_counts$brier_stratified))
settings <- default_survival_scenarios()
reversed <- run_survival_stress(8, 400, 123, settings[4:1, ])
stopifnot(identical(sort_records(paired), sort_records(reversed)))
single <- run_survival_stress(8, 400, 123, settings[4, ])
stopifnot(identical(sort_records(single), sort_records(fast)))
expect_error(run_survival_stress(1))

small <- unchanged[1:2, ]
small$realised_stratified_eur <- c(10, 30)
small$realised_immediate_eur <- c(15, 20)
small$bias_stratified <- c(0.1, 0.3)
set.seed(17)
summary <- summarize_survival_stress(small, 100)
stopifnot(summary$stratified_minus_immediate_mean_eur == 2.5,
          summary$stratified_below_immediate_fraction == 0.5,
          isTRUE(all.equal(summary$stratified_minus_immediate_p10_eur, -3.5)),
          isTRUE(all.equal(summary$mean_bias_stratified, 0.2)))
expect_error(summarize_survival_stress(paired[-1, ]))
expect_error(summarize_survival_stress(rbind(paired, paired[1, ])))
expect_error(summarize_survival_stress(transform(paired, brier_stratified = NA_real_)))
bad <- paired
bad$sale_day_stratified[1:2] <- c(12, 28)
expect_error(summarize_survival_stress(bad))

# Saved lot-level measurements reproduce the report with the recorded bootstrap.
directory <- "results/survival_stress"
saved <- utils::read.csv(file.path(directory, "records.csv"), stringsAsFactors = FALSE)
saved_settings <- dget(file.path(directory, "settings.R"))
stopifnot(nrow(saved) == saved_settings$n_lots * nrow(saved_settings$scenarios))
set.seed(saved_settings$bootstrap_seed)
rebuilt <- summarize_survival_stress(saved, saved_settings$n_boot)
committed <- utils::read.csv(file.path(directory, "summary.csv"), stringsAsFactors = FALSE)
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange storage survival stress tests passed.\n")
