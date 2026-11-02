# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

inventory <- data.frame(cohort = c("advanced", "intermediate"),
                        mass_kg = c(300, 550), initially_sellable = TRUE,
                        shape = c(2, 2), scale = c(18, 36))
prices <- expand.grid(cohort = inventory$cohort, day = c(12, 16, 28),
                       KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
prices$price_eur_per_kg <- c(1, 2, 3, 4, 5, 6)

# No-error prices preserve every quote and do not consume random numbers.
set.seed(12)
state <- .Random.seed
stopifnot(identical(apply_price_error(prices, inventory, 12), prices))
stopifnot(identical(state, .Random.seed))

# Independently calculated multipliers on an irregular observation grid.
actual <- apply_price_error(prices, inventory, 12, 0.8, 0.2, c(2, -1))
expected <- c(1, 0.8^0.25 * exp(0.2 - 0.04 * 0.25 / 2),
              0.8 * exp(0.2 * (1 - sqrt(0.75)) - 0.04 / 2))
stopifnot(isTRUE(all.equal(actual$price_eur_per_kg / prices$price_eur_per_kg,
                          rep(expected, each = 2))))
shuffled <- apply_price_error(prices[6:1, ], inventory, 12, 0.8, 0.2, c(2, -1))
stopifnot(isTRUE(all.equal(shuffled$price_eur_per_kg,
                          rev(actual$price_eur_per_kg))))

# Numerically integrate the actual transform against a normal density: its
# expected terminal quote must be m times forecast, despite log-price variance.
two_days <- prices[prices$day != 16, ]
expectation <- stats::integrate(function(z) {
  vapply(z, function(innovation) {
    path <- apply_price_error(two_days, inventory, 12, 0.8, 0.4, innovation)
    path$price_eur_per_kg[3] / two_days$price_eur_per_kg[3]
  }, numeric(1)) * stats::dnorm(z)
}, -8, 8)$value
stopifnot(abs(expectation - 0.8) < 1e-8)

expect_error(apply_price_error(prices, inventory, 13))
expect_error(apply_price_error(prices[-1, ], inventory, 12))
expect_error(apply_price_error(prices, inventory, 12, 0))
expect_error(apply_price_error(prices, inventory, 12, terminal_log_sd = -1))
expect_error(apply_price_error(prices, inventory, 12, innovations = 1))
expect_error(apply_price_error(prices, inventory, 12, innovations = c(NA, 1)))
expect_error(validate_price_scenarios(rbind(default_price_scenarios(),
                                           default_price_scenarios()[1, ])))
expect_error(run_price_sensitivity(1))

# An extreme adverse future path must change evaluation, never trigger a new
# optimisation. The current quote and hence immediate-sale revenue stay fixed.
set.seed(400)
lot <- simulate_policy_lot(1)
lot$stratified_day <- 20L
lot$pooled_day <- 16L
lot$oracle_day <- 20L
original <- score_policy_lot(lot)
crash <- lot$prices
crash$price_eur_per_kg[crash$day > lot$decision_day] <- 0
optimise <- optimal_batch_sale
optimal_batch_sale <- function(...) stop("scoring must not reselect a policy")
crashed <- score_policy_lot(lot, crash)
optimal_batch_sale <- optimise
stopifnot(crashed$sale_day_stratified == 20L, crashed$sale_day_pooled == 16L)
stopifnot(crashed$realised_stratified_eur == -850 * 0.001 * (20 - 12 + 2))
stopifnot(crashed$realised_pooled_eur == -850 * 0.001 * (16 - 12 + 2))
stopifnot(crashed$realised_immediate_eur == original$realised_immediate_eur)

# The original seeded lots and perfect-price results must be preserved.
baseline <- run_policy_experiment(8, 400)
paired <- run_price_sensitivity(8, 400, 123)
perfect <- paired[paired$scenario == "perfect_forecast", ]
keep <- names(baseline)[!grepl("oracle", names(baseline))]
rownames(perfect) <- NULL
stopifnot(identical(baseline[keep], perfect[keep]))
stopifnot(all(perfect$price_impact_stratified_eur == 0))
stopifnot(!any(grepl("oracle", names(paired))))
stopifnot(any(baseline$sale_day_stratified > 12))

other_errors <- run_price_sensitivity(8, 400, 456)
fixed <- c("lot_id", "sale_day_stratified", "sale_day_pooled",
           "realised_immediate_eur", "brier_stratified", "brier_pooled",
           "log_loss_stratified", "log_loss_pooled")
stopifnot(identical(paired[fixed], other_errors[fixed]))
stopifnot(any(paired$realised_stratified_eur != other_errors$realised_stratified_eur))
for (id in unique(paired$lot_id)) {
  rows <- paired[paired$lot_id == id, fixed]
  stopifnot(nrow(unique(rows)) == 1L)
}

# Scenario order/number cannot influence the paired lots or innovations.
scenarios <- default_price_scenarios()
reversed <- run_price_sensitivity(8, 400, 123, scenarios[4:1, ])
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
stopifnot(identical(sort_records(paired), sort_records(reversed)))
single <- run_price_sensitivity(8, 400, 123, scenarios[3, ])
stopifnot(identical(sort_records(single),
                    sort_records(paired[paired$scenario == scenarios$scenario[3], ])))

# Hand-worked paired contrasts and downside statistics, including exact ties.
small <- perfect[1:2, ]
small$realised_stratified_eur <- c(10, 30)
small$realised_pooled_eur <- c(20, 20)
small$realised_immediate_eur <- c(15, 20)
set.seed(20)
summary <- summarize_price_sensitivity(small, 200)
stopifnot(summary$stratified_minus_pooled_eur == 0)
stopifnot(summary$stratified_minus_immediate_eur == 2.5)
stopifnot(summary$stratified_below_immediate_fraction == 0.5)
stopifnot(summary$pooled_below_immediate_fraction == 0)
stopifnot(isTRUE(all.equal(summary$stratified_minus_immediate_p10_eur, -3.5)))
stopifnot(summary$pooled_contrast_lower_95 >= -10,
          summary$pooled_contrast_upper_95 <= 10)
expect_error(summarize_price_sensitivity(paired[-1, ]))
expect_error(summarize_price_sensitivity(rbind(paired, paired[1, ])))
bad <- paired
bad$realised_stratified_eur[1] <- Inf
expect_error(summarize_price_sensitivity(bad))

# Saved measurements reproduce the summary from the recorded bootstrap seed.
directory <- "results/price_sensitivity"
saved <- utils::read.csv(file.path(directory, "records.csv"), stringsAsFactors = FALSE)
settings <- dget(file.path(directory, "settings.R"))
stopifnot(nrow(saved) == settings$n_lots * nrow(settings$scenarios))
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_price_sensitivity(saved, settings$n_boot)
committed <- utils::read.csv(file.path(directory, "summary.csv"), stringsAsFactors = FALSE)
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))
stopifnot(all(saved$price_impact_stratified_eur[saved$scenario == "perfect_forecast"] == 0))
for (id in unique(saved$lot_id)) {
  stopifnot(nrow(unique(saved[saved$lot_id == id, fixed])) == 1L)
}

cat("Orange storage price sensitivity tests passed.\n")
