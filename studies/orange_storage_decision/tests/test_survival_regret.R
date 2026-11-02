# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/robust_policy.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")
source("R/survival_regret.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

# Analytical one-stratum example: nominal values are 100, 99, 90 at ages
# 12/16/20. Scaling the exponential lifetime gives V_m(t)=V_1(t)*exp(t*(1-1/m)/10).
# The nominal rule chooses 12, whereas the minimax-regret compromise chooses 16.
stock <- data.frame(cohort = "eligible", mass_kg = 100, initially_sellable = TRUE, shape = 1, scale = 10)
days <- c(12L, 16L, 20L)
prices <- data.frame(cohort = "eligible", day = days, price_eur_per_kg = c(100, 99, 90) / (100 * exp(-days / 10)))
factors <- c(0.75, 1, 1.25)
expected <- vapply(factors, function(m) c(100, 99, 90) * exp(days * (1 - 1 / m) / 10), numeric(3))
choice <- minimax_survival_regret_sale(stock, prices, factors, 0, 12, 0)
stopifnot(choice$decision$sale_day == 16, optimal_batch_sale(stock, prices, 0, 12, 0)$sale_day == 12,
          max(abs(choice$scenario_values$expected_net_eur - as.vector(expected))) < 1e-10)
regrets <- sweep(-expected, 2, apply(expected, 2, max), "+")
stopifnot(max(abs(choice$grid$worst_regret_eur - apply(regrets, 1, max))) < 1e-10)
# Lag and physical holding costs are identical across scenarios, even when
# expected acceptable mass differs. Earliest dates resolve exact criterion ties.
with_cost <- minimax_survival_regret_sale(stock, prices, factors, 0.01, 12, 2)
lag_values <- sweep(expected, 2, exp(-2 / (10 * factors)), "*") - (days - 12 + 2)
stopifnot(max(abs(with_cost$scenario_values$expected_net_eur - as.vector(lag_values))) < 1e-10,
          minimax_survival_regret_sale(stock, prices[1, ], factors)$decision$sale_day == 12,
          minimax_survival_regret_sale(stock, transform(prices, price_eur_per_kg = 0), factors, 0)$decision$sale_day == 12)
single <- minimax_survival_regret_sale(stock, prices, 1, 0.01, 12, 2)
stopifnot(single$decision$sale_day == optimal_batch_sale(stock, prices, 0.01, 12, 2)$sale_day,
          identical(choice, minimax_survival_regret_sale(stock, prices[3:1, ], rev(factors), 0, 12, 0)))
set.seed(750)
rng <- .Random.seed
invisible(minimax_survival_regret_sale(stock, prices))
stopifnot(identical(rng, .Random.seed))
expect_error(minimax_survival_regret_sale(stock, prices, c(1, 1)))
expect_error(minimax_survival_regret_sale(stock, prices, c(0, 1)))
expect_error(minimax_survival_regret_sale(stock, prices[-1, ]))
expect_error(minimax_regret_grids(list(a = data.frame(sale_day = c(1, 1), expected_net_eur = c(1, 2)))))
expect_error(minimax_regret_grids(list(a = data.frame(sale_day = 1, expected_net_eur = Inf))))
expect_error(minimax_regret_grids(list(a = data.frame(sale_day = 1, expected_net_eur = 1),
  b = data.frame(sale_day = 2, expected_net_eur = 2))))

# Historical ID/calendar protection applies to the new rule too.
history <- simulate_historical_inspections(4, 751)
model <- fit_historical_survival(history, historical_study_inventory(), 0, 0.9, 0.9)
set.seed(752)
public_prices <- simulate_price_scenario()
expect_error(historical_minimax_sale(model, model$training_lot_ids[1], historical_study_inventory(), public_prices, 0))
future <- model
future$fit_calendar_day <- 13
expect_error(historical_minimax_sale(future, "new", historical_study_inventory(), public_prices, 0))
stopifnot(identical(historical_minimax_sale(model, "new", historical_study_inventory(), public_prices, 0),
  historical_minimax_sale(model, "new", transform(historical_study_inventory(), shape = 9, scale = 999), public_prices, 0)))

# One archive is fitted before either policy; all dates precede target outcomes.
original_fit <- fit_historical_survival
original_nominal <- historical_sale_decision
original_robust <- historical_minimax_sale
original_lifetimes <- simulate_fruit_lifetimes
fits <- 0L
decisions <- 0L
fit_historical_survival <- function(history, ...) {
  fits <<- fits + 1L
  stopifnot(decisions == 0L, all(history$harvest_day + history$day < 0L))
  original_fit(history, ...)
}
check_information <- function(model, lot_id, inventory) {
  decisions <<- decisions + 1L
  stopifnot(fits == 1L, !lot_id %in% model$training_lot_ids, all(inventory$shape == 1), all(inventory$scale == 1))
}
historical_sale_decision <- function(model, lot_id, inventory, ...) {
  check_information(model, lot_id, inventory)
  original_nominal(model, lot_id, inventory, ...)
}
historical_minimax_sale <- function(model, lot_id, inventory, ...) {
  check_information(model, lot_id, inventory)
  original_robust(model, lot_id, inventory, ...)
}
simulate_fruit_lifetimes <- function(...) {
  stopifnot(fits == 1L, decisions == 6L)
  original_lifetimes(...)
}
first <- run_survival_regret_replication(1, 3, 4, factors, c(0.6, 1, 1.4), 753, 754, 755)
fit_historical_survival <- original_fit
historical_sale_decision <- original_nominal
historical_minimax_sale <- original_robust
simulate_fruit_lifetimes <- original_lifetimes
other <- run_survival_regret_replication(1, 3, 4, factors, c(0.6, 1, 1.4), 753, 754, 756)
fixed <- c("lot_id", "nominal_day", "robust_day", "fitted_nominal_worst_regret_eur", "fitted_robust_worst_regret_eur")
stopifnot(identical(first$records[fixed], other$records[fixed]), identical(first$fits, other$fits),
          any(first$records$robust_return_eur != other$records$robust_return_eur))
point <- run_survival_regret_replication(1, 3, 4, 1, c(0.6, 1, 1.4), 753, 754, 755)
stopifnot(all(point$records$robust_day == point$records$nominal_day), all(point$records$robust_minus_nominal_eur == 0),
          identical(first$records$nominal_return_eur, point$records$nominal_return_eur))
second <- run_survival_regret_replication(2, 3, 4, factors, c(0.6, 1, 1.4), 757, 758, 759)
records <- rbind(first$records, second$records)
set.seed(760)
summary <- summarize_survival_regret(records, 200L)
set.seed(760)
stopifnot(identical(summary, summarize_survival_regret(records[nrow(records):1, ], 200L)))
expect_error(summarize_survival_regret(records[-1, ]))
expect_error(summarize_survival_regret(rbind(records, records[1, ])))
expect_error(summarize_survival_regret(transform(records, robust_minus_nominal_eur = 999)))
bad <- records
bad$robust_day[1] <- bad$robust_day[1] + 1
expect_error(summarize_survival_regret(bad))

# Hand-calculated independent block differences +100 and -100 have mean zero.
# Duplicating targets inside blocks cannot supply independent training archives.
manual <- records
manual$nominal_return_eur <- 200
manual$day12_return_eur <- 150
manual$robust_return_eur <- ifelse(manual$repetition == 1, 300, 100)
manual$robust_minus_nominal_eur <- manual$robust_return_eur - 200
manual$nominal_minus_day12_eur <- 50
manual$robust_minus_day12_eur <- manual$robust_return_eur - 150
manual$robust_below_nominal <- manual$robust_below_day12 <- as.integer(manual$repetition == 2)
manual$nominal_below_day12 <- 0
set.seed(761)
expected_summary <- summarize_survival_regret(manual, 200L)
delta <- expected_summary$summary[expected_summary$summary$metric == "robust_minus_nominal_eur", ]
stopifnot(all(delta$mean == 0), all(delta$lower_95 == -100), all(delta$upper_95 == 100))
duplicate <- manual
duplicate$lot_id <- paste0(duplicate$lot_id, "-copy")
set.seed(761)
expanded <- summarize_survival_regret(rbind(manual, duplicate), 200L)
stopifnot(isTRUE(all.equal(expected_summary$summary, expanded$summary, tolerance = 1e-12)),
          all(expanded$repetitions$n_targets == 6L))

# Reconstruct every published fit and interval and one complete target panel.
path <- "results/survival_regret"
settings <- dget(file.path(path, "settings.R"))
seeds <- read.csv(file.path(path, "seeds.csv"))
counts <- read.csv(file.path(path, "counts.csv"))
saved_fits <- read.csv(file.path(path, "fits.csv"))
saved <- read.csv(file.path(path, "records.csv"))
stopifnot(identical(seeds, archive_seed_manifest(settings$n_repeats, settings$master_seed)),
          nrow(saved) == settings$n_repeats * settings$n_targets * length(settings$evaluation_multipliers))
for (i in seq_len(settings$n_repeats)) {
  rebuilt <- fit_weibull_by_cohort(counts[counts$repetition == i, ], historical_study_inventory(), 0.9, 0.9)
  stored <- saved_fits[saved_fits$repetition == i, names(rebuilt)]
  rownames(stored) <- NULL
  stopifnot(isTRUE(all.equal(rebuilt, stored, tolerance = 1e-6)))
}
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_survival_regret(saved, settings$n_boot)
for (name in names(rebuilt)) {
  stopifnot(isTRUE(all.equal(rebuilt[[name]], read.csv(file.path(path, paste0(name, ".csv"))), tolerance = 1e-10)))
}
one <- run_survival_regret_replication(1, settings$n_targets, settings$n_history, settings$decision_multipliers,
  settings$evaluation_multipliers, seeds$history_seed[1], seeds$metadata_seed[1], seeds$fruit_seed[1])
reference <- saved[saved$repetition == 1, ]
fitted_fields <- c("fitted_nominal_worst_regret_eur", "fitted_robust_worst_regret_eur")
stable_fields <- setdiff(names(reference), fitted_fields)
stopifnot(isTRUE(all.equal(one$records[stable_fields], reference[stable_fields], tolerance = 1e-10)),
          max(abs(as.matrix(one$records[fitted_fields]) - as.matrix(reference[fitted_fields]))) < 1e-4)
cat("Orange survival regret tests passed.\n")
