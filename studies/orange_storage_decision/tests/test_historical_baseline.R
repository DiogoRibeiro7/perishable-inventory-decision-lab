# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shape_ensemble.R")
source("R/inspection_removals.R")
source("R/inspection_plan_value.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

stock <- historical_study_inventory()
history <- simulate_historical_inspections(4, 720)
model <- fit_historical_survival(history, stock, 0, 0.9, 0.9)
stopifnot(length(model$training_lot_ids) == 4L, model$n_training_checks == 4 * 720,
          all(model$counts$n_checked == 240), max(history$day) == 24,
          max(history$harvest_day + history$day) < 0,
          isTRUE(all.equal(model, fit_historical_survival(history[nrow(history):1, ], stock, 0, 0.9, 0.9))))
# Historical fruit age may exceed the target decision age, provided the observation
# was already available on the calendar. Duplicate IDs/rows and future data fail.
expect_error(fit_historical_survival(transform(history, harvest_day = 0), stock, 0, 0.9, 0.9))
bad <- history
bad$harvest_day[1] <- -999
expect_error(fit_historical_survival(bad, stock))
expect_error(fit_historical_survival(rbind(history, history[1, ]), stock))
expect_error(fit_historical_survival(history[history$lot_id == history$lot_id[1], ], stock))
expect_error(fit_historical_survival(transform(history, lot_id = NA_character_), stock))
expect_error(historical_fitted_inventory(model, model$training_lot_ids[1], stock, 0, 12))
future_model <- model
future_model$fit_calendar_day <- 13
expect_error(historical_fitted_inventory(future_model, "new-lot", stock, 0, 12))
expect_error(historical_fitted_inventory(model, "new-lot", stock, 0.5, 12))

set.seed(24)
prices <- simulate_price_scenario()
before <- model
choice <- historical_sale_decision(model, "new-lot", stock, prices, 0)
fitted <- historical_fitted_inventory(model, "new-lot", stock, 0, 12)
stopifnot(identical(model, before),
          isTRUE(all.equal(choice, optimal_batch_sale(fitted, prices, 0.001, 12, 2))),
          identical(choice, historical_sale_decision(model, "new-lot",
            transform(stock, shape = 9, scale = 1000), prices, 0)))

# Proper scoring uses fruit-level outcomes and inventory weights, not squared
# error of an aggregate fraction. At probability 1/2, Brier is exactly 1/4.
tiny <- data.frame(cohort = c("a", "b"), mass_kg = c(0.4, 0.6),
  initially_sellable = TRUE, shape = 1, scale = 16 / log(2))
scores <- historical_forecast_records("new-lot", tiny, list(a = c(0, 30), b = c(0, 40, 50)))
stopifnot(abs(scores$predicted_kg[1] - 0.5) < 1e-12,
          abs(scores$accepted_kg[1] - 0.6) < 1e-12,
          abs(scores$brier[1] - 0.25) < 1e-12,
          abs(scores$log_loss[1] - log(2)) < 1e-12)

# Freeze one model and all historical dates before any target lifetimes exist.
original_fit <- fit_historical_survival
original_decision <- historical_sale_decision
original_lifetimes <- simulate_fruit_lifetimes
fits <- 0L
decisions <- 0L
fit_historical_survival <- function(...) {
  fits <<- fits + 1L
  original_fit(...)
}
historical_sale_decision <- function(model, lot_id, inventory, prices, harvest_day, ...) {
  decisions <<- decisions + 1L
  stopifnot(fits == 1L, all(inventory$shape == 1), all(inventory$scale == 1),
            !lot_id %in% model$training_lot_ids)
  original_decision(model, lot_id, inventory, prices, harvest_day, ...)
}
simulate_fruit_lifetimes <- function(...) {
  stopifnot(fits == 1L, decisions == 2L)
  original_lifetimes(...)
}
result <- run_historical_experiment(2, 4, 721, 811, 812, 813)
fit_historical_survival <- original_fit
historical_sale_decision <- original_decision
simulate_fruit_lifetimes <- original_lifetimes
stopifnot(nrow(result$records) == 2L, nrow(result$forecasts) == 6L,
          !any(result$records$lot_id %in% result$model$training_lot_ids))
other <- run_historical_experiment(2, 4, 721, 811, 814, 813)
stopifnot(identical(result$model, other$model), identical(result$history, other$history),
          identical(result$records$sale_day_historical, other$records$sale_day_historical),
          any(result$records$return_historical_eur != other$records$return_historical_eur))
expect_error(run_historical_experiment(1))

manual <- result$records
manual$return_historical_eur <- c(100, 120)
manual$return_day12_eur <- c(90, 130)
set.seed(921)
summary <- summarize_historical_returns(manual, 100)
stopifnot(summary$gain_mean_eur[1] == 0, summary$below_comparator_fraction[1] == 0.5)
set.seed(921)
stopifnot(identical(summary, summarize_historical_returns(manual[2:1, ], 100)))
expect_error(summarize_historical_returns(rbind(manual, manual[1, ])))
expect_error(summarize_historical_returns(transform(manual, return_historical_eur = Inf)))
expect_error(summarize_historical_forecasts(result$forecasts[-1, ]))
expect_error(summarize_historical_forecasts(transform(result$forecasts, day = 12)))

# Reconstruct the published model and conditional target-lot intervals.
path <- "results/historical_baseline"
settings <- dget(file.path(path, "settings.R"))
archive <- read.csv(file.path(path, "history.csv"))
saved <- read.csv(file.path(path, "records.csv"))
future <- read.csv(file.path(path, "forecasts.csv"))
rebuilt_model <- fit_historical_survival(archive, historical_study_inventory(),
  settings$fit_calendar_day, settings$sensitivity, settings$specificity)
stopifnot(length(unique(archive$lot_id)) == settings$n_history,
          nrow(saved) == settings$n_lots, nrow(future) == 3L * settings$n_lots,
          !any(saved$lot_id %in% rebuilt_model$training_lot_ids),
          isTRUE(all.equal(rebuilt_model$fits, read.csv(file.path(path, "fits.csv")), tolerance = 1e-6)))
set.seed(settings$bootstrap_seed)
rebuilt_returns <- summarize_historical_returns(saved, settings$n_boot)
rebuilt_forecasts <- summarize_historical_forecasts(future, settings$n_boot)
stopifnot(isTRUE(all.equal(rebuilt_returns, read.csv(file.path(path, "return_summary.csv")), tolerance = 1e-10)),
          isTRUE(all.equal(rebuilt_forecasts, read.csv(file.path(path, "forecast_summary.csv")), tolerance = 1e-10)))
cat("Orange historical baseline tests passed.\n")
