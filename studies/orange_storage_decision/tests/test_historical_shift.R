# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

times <- list(a = c(10, 20), b = c(12, 24, 36))
stopifnot(identical(scale_fruit_lifetimes(times, 1), times),
          identical(scale_fruit_lifetimes(times, 0.75), list(a = c(7.5, 15), b = c(9, 18, 27))),
          identical(names(scale_fruit_lifetimes(times, 1.25)), names(times)))
expect_error(scale_fruit_lifetimes(times, 0))
expect_error(scale_fruit_lifetimes(list(a = c(1, Inf)), 1))
expect_error(scale_fruit_lifetimes(list(a = c(-1, 1)), 1))
expect_error(scale_fruit_lifetimes(unname(times), 1))
expect_error(scale_fruit_lifetimes(list(a = .Machine$double.xmax), 2))
expect_error(run_historical_shift_experiment(1))
expect_error(run_historical_shift_experiment(2, 1))
expect_error(run_historical_shift_experiment(2, 2, multipliers = c(0.75, 1.25)))
expect_error(run_historical_shift_experiment(2, 2, multipliers = c(1, 1)))

# Five known 0.2 kg fruit, price EUR 1/kg. Quality is assessed two days after
# sale, with strict T > delivery age. Holding starts at harvest for every policy.
stock <- data.frame(cohort = c("a", "b"), mass_kg = c(0.4, 0.6),
  initially_sellable = TRUE, shape = 1, scale = 16 / log(2))
prices <- expand.grid(cohort = c("a", "b"), day = c(12L, 16L), stringsAsFactors = FALSE)
prices$price_eur_per_kg <- 1
lot <- list(lot_id = "toy", truth = stock, prices = prices, fitted = stock, sale_day = 16L)
short <- score_historical_shift(lot, times, 0.75, 1L)
same <- score_historical_shift(lot, times, 1, 1L)
long <- score_historical_shift(lot, times, 1.25, 1L)
stopifnot(abs(short$return_eur - 0.182) < 1e-12, abs(short$return_day12_eur - 0.586) < 1e-12,
          abs(same$return_eur - 0.582) < 1e-12, abs(long$return_day12_eur - 0.786) < 1e-12,
          abs(short$accepted_day20_kg - 0.2) < 1e-12,
          abs(same$accepted_day20_kg - 0.4) < 1e-12,
          abs(long$accepted_day20_kg - 0.6) < 1e-12,
          short$predicted_day20_kg == same$predicted_day20_kg,
          same$predicted_day20_kg == long$predicted_day20_kg)

# Fit once before targets; all target decisions must precede all fruit outcomes.
original_fit <- fit_historical_survival
original_decision <- historical_sale_decision
original_lifetimes <- simulate_fruit_lifetimes
fits <- 0L
decisions <- 0L
fit_historical_survival <- function(history, ...) {
  fits <<- fits + 1L
  stopifnot(decisions == 0L, all(history$harvest_day + history$day < 0L))
  original_fit(history, ...)
}
historical_sale_decision <- function(model, lot_id, inventory, prices, harvest_day, ...) {
  decisions <<- decisions + 1L
  stopifnot(fits == 1L, !lot_id %in% model$training_lot_ids,
            all(inventory$shape == 1), all(inventory$scale == 1))
  original_decision(model, lot_id, inventory, prices, harvest_day, ...)
}
simulate_fruit_lifetimes <- function(...) {
  stopifnot(fits == 1L, decisions == 3L)
  original_lifetimes(...)
}
first <- run_historical_shift_replication(1, 3, 4, c(0.75, 1, 1.25), 741, 742, 743)
fit_historical_survival <- original_fit
historical_sale_decision <- original_decision
simulate_fruit_lifetimes <- original_lifetimes
other_fruit <- run_historical_shift_replication(1, 3, 4, c(0.75, 1, 1.25), 741, 742, 744)
stopifnot(identical(first$counts, other_fruit$counts), identical(first$fits, other_fruit$fits),
          identical(first$records$sale_day, other_fruit$records$sale_day),
          identical(first$records$predicted_day20_kg, other_fruit$records$predicted_day20_kg),
          any(first$records$return_eur != other_fruit$records$return_eur))
other_shifts <- run_historical_shift_replication(1, 3, 4, c(0.6, 1, 1.4), 741, 742, 743)
stopifnot(identical(first$fits, other_shifts$fits), identical(first$records$sale_day, other_shifts$records$sale_day),
          identical(first$records[first$records$lifetime_multiplier == 1, ],
            other_shifts$records[other_shifts$records$lifetime_multiplier == 1, ]))
second <- run_historical_shift_replication(2, 3, 4, c(0.75, 1, 1.25), 745, 746, 747)
records <- rbind(first$records, second$records)
set.seed(748)
summary <- summarize_historical_shift(records, 200L)
set.seed(748)
stopifnot(identical(summary, summarize_historical_shift(records[nrow(records):1, ], 200L)),
          nrow(summary$repetitions) == 6L, all(summary$repetitions$n_targets == 3L))
expect_error(summarize_historical_shift(records[-1, ]))
expect_error(summarize_historical_shift(rbind(records, records[1, ])))
expect_error(summarize_historical_shift(transform(records, bias_day20_kg = Inf)))
expect_error(summarize_historical_shift(transform(records, gain_day12_eur = 999)))
bad <- records
bad$sale_day[1] <- bad$sale_day[1] + 1
expect_error(summarize_historical_shift(bad))
bad <- records
bad$lot_id[bad$repetition == 2] <- sub("shift-002", "shift-001", bad$lot_id[bad$repetition == 2])
expect_error(summarize_historical_shift(bad))

# Known paired repetition differences +0.1 and -0.1. Replicating targets inside
# a block must not create extra independent training archives or tighter CIs.
manual <- records
manual$brier <- 0.2
manual$brier[manual$lifetime_multiplier == 0.75] <-
  ifelse(manual$repetition[manual$lifetime_multiplier == 0.75] == 1, 0.3, 0.1)
set.seed(749)
expected <- summarize_historical_shift(manual, 200L)
delta <- expected$contrasts[expected$contrasts$metric == "brier" & expected$contrasts$lifetime_multiplier == 0.75, ]
stopifnot(abs(delta$mean) < 1e-12, abs(delta$lower_95 + 0.1) < 1e-12, abs(delta$upper_95 - 0.1) < 1e-12)
duplicate <- manual
duplicate$lot_id <- paste0(duplicate$lot_id, "-copy")
set.seed(749)
expanded <- summarize_historical_shift(rbind(manual, duplicate), 200L)
stopifnot(isTRUE(all.equal(expected$summary, expanded$summary, tolerance = 1e-12)),
          isTRUE(all.equal(expected$contrasts, expanded$contrasts, tolerance = 1e-12)),
          all(expanded$repetitions$n_targets == 6L))

# Rebuild every saved fit and interval, and audit the physical coupling of every
# target. Larger multipliers cannot reduce acceptable mass at any fixed age.
path <- "results/historical_shift"
settings <- dget(file.path(path, "settings.R"))
seeds <- read.csv(file.path(path, "seeds.csv"))
stopifnot(identical(seeds, archive_seed_manifest(settings$n_repeats, settings$master_seed)))
counts <- read.csv(file.path(path, "counts.csv"))
saved_fits <- read.csv(file.path(path, "fits.csv"))
saved <- read.csv(file.path(path, "records.csv"))
stopifnot(nrow(saved) == length(settings$lifetime_multipliers) * settings$n_repeats * settings$n_targets,
          length(unique(saved$lot_id)) == settings$n_repeats * settings$n_targets)
for (i in seq_len(settings$n_repeats)) {
  part <- counts[counts$repetition == i, ]
  rebuilt <- fit_weibull_by_cohort(part, historical_study_inventory(), settings$sensitivity, settings$specificity)
  stored <- saved_fits[saved_fits$repetition == i, names(rebuilt)]
  rownames(stored) <- NULL
  stopifnot(all(part$n_checked == settings$n_history * settings$historical_checks_per_group),
            isTRUE(all.equal(rebuilt, stored, tolerance = 1e-6)))
}
for (lot in split(saved, saved$lot_id)) {
  lot <- lot[order(lot$lifetime_multiplier), ]
  for (field in c("return_eur", "return_day12_eur", "return_day16_eur",
                   "accepted_day16_kg", "accepted_day20_kg", "accepted_day24_kg")) {
    stopifnot(all(diff(lot[[field]]) >= -1e-10))
  }
}
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_historical_shift(saved, settings$n_boot)
for (name in names(rebuilt)) {
  stopifnot(isTRUE(all.equal(rebuilt[[name]], read.csv(file.path(path, paste0(name, ".csv"))), tolerance = 1e-10)))
}
# Reproduce one complete train/test repetition, including target prices/outcomes.
one <- run_historical_shift_replication(1, settings$n_targets, settings$n_history,
  settings$lifetime_multipliers, seeds$history_seed[1], seeds$metadata_seed[1], seeds$fruit_seed[1])
reference <- saved[saved$repetition == 1, ]
# Refitting involves iterative optimisation: numerical-library/build differences
# can perturb fitted probabilities while leaving the sampled fruit and decisions
# unchanged. Bound each fitted output absolutely, below the report's precision;
# retain strict checks for IDs, scenarios, sale dates, realised masses and EUR.
forecast_mass <- c(paste0("predicted_day", c(16L, 20L, 24L), "_kg"),
  paste0("bias_day", c(16L, 20L, 24L), "_kg"))
forecast_scores <- c("brier", "log_loss")
check_reconstruction <- function(actual, expected) {
  stopifnot(identical(names(actual), names(expected)), nrow(actual) == nrow(expected))
  differences <- setNames(numeric(ncol(expected)), names(expected))
  exact <- c("lot_id", "repetition", "lifetime_multiplier", "sale_day", "below_day12")
  for (field in names(expected)) {
    if (field %in% exact) {
      if (anyNA(actual[[field]]) || !all(actual[[field]] == expected[[field]])) {
        stop(sprintf("reconstruction changed %s", field), call. = FALSE)
      }
      next
    }
    # 0.1 g for fitted masses and 1e-7 for proper scores, both well below the
    # report's displayed resolution. Realised outcomes stay at 1e-10.
    tolerance <- if (field %in% forecast_mass) 1e-4 else if (field %in% forecast_scores) 1e-7 else 1e-10
    difference <- abs(actual[[field]] - expected[[field]])
    if (any(!is.finite(difference)) || any(difference > tolerance)) {
      stop(sprintf("reconstruction %s: max absolute difference %.12g exceeds %.12g",
        field, max(difference), tolerance), call. = FALSE)
    }
    differences[field] <- max(difference)
  }
  differences
}
differences <- check_reconstruction(one$records, reference)
cat(sprintf("Reconstruction maximum fitted-mass difference: %.12g kg; score difference: %.12g\n",
  max(differences[forecast_mass]), max(differences[forecast_scores])))
# Small numerical fitting variation is tolerated; changed decisions, sampled
# fruit, money or materially different forecasts must still fail this check.
rounded_fit <- reference
rounded_fit[forecast_mass] <- rounded_fit[forecast_mass] + 1e-5
rounded_fit[forecast_scores] <- rounded_fit[forecast_scores] + 1e-8
invisible(check_reconstruction(rounded_fit, reference))
for (field in c("sale_day", "return_eur", "accepted_day20_kg", "predicted_day20_kg", "brier")) {
  changed <- reference
  changed[[field]][1] <- changed[[field]][1] + if (field == "brier") 1e-5 else 0.2
  expect_error(check_reconstruction(changed, reference))
}
changed <- reference
changed$lot_id[1] <- "different-target"
expect_error(check_reconstruction(changed, reference))
cat("Orange historical shift tests passed.\n")
