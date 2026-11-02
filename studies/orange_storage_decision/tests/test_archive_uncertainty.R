# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

seeds <- archive_seed_manifest(3L, 730L)
stopifnot(identical(seeds, archive_seed_manifest(3L, 730L)),
          !anyDuplicated(unlist(seeds[-1])), nrow(seeds) == 3L)
expect_error(run_archive_experiment(1))
expect_error(run_archive_experiment(2, 1))
expect_error(run_archive_experiment(2, 2, c(10, 10)))
expect_error(run_archive_experiment(2, 2, c(100, 10)))

# Prove that nested training data precede all target decisions, and every
# decision precedes every target outcome. The policy sees no latent parameters.
original_fit <- fit_historical_survival
original_decision <- historical_sale_decision
original_lifetimes <- simulate_fruit_lifetimes
archives <- list()
decisions <- 0L
fit_historical_survival <- function(history, ...) {
  archives[[length(archives) + 1L]] <<- history
  stopifnot(decisions == 0L, all(history$harvest_day + history$day < 0L))
  original_fit(history, ...)
}
historical_sale_decision <- function(model, lot_id, inventory, prices, harvest_day, ...) {
  decisions <<- decisions + 1L
  stopifnot(length(archives) == 2L, all(inventory$shape == 1), all(inventory$scale == 1),
            !lot_id %in% model$training_lot_ids)
  original_decision(model, lot_id, inventory, prices, harvest_day, ...)
}
simulate_fruit_lifetimes <- function(...) {
  stopifnot(decisions == 6L, length(archives) == 2L)
  original_lifetimes(...)
}
first <- run_archive_replication(1, 3, c(2, 4), 731, 732, 733)
fit_historical_survival <- original_fit
historical_sale_decision <- original_decision
simulate_fruit_lifetimes <- original_lifetimes
stopifnot(length(unique(archives[[1]]$lot_id)) == 2L,
          length(unique(archives[[2]]$lot_id)) == 4L,
          identical(archives[[1]], archives[[2]][archives[[2]]$lot_id %in% archives[[1]]$lot_id, ]),
          !any(first$records$lot_id %in% archives[[2]]$lot_id))
other_fruit <- run_archive_replication(1, 3, c(2, 4), 731, 732, 734)
stopifnot(identical(first$fits, other_fruit$fits), identical(first$counts, other_fruit$counts),
          identical(first$records$sale_day, other_fruit$records$sale_day),
          any(first$records$return_eur != other_fruit$records$return_eur))
second <- run_archive_replication(2, 3, c(2, 4), 735, 736, 737)
records <- rbind(first$records, second$records)
blocks <- archive_repetition_means(records)
stopifnot(nrow(blocks) == 4L, all(blocks$n_targets == 3L),
          all(first$counts$n_checked[first$counts$training_lots == 2] == 120),
          all(first$counts$n_checked[first$counts$training_lots == 4] == 240))
set.seed(738)
summary <- summarize_archive_experiment(records, 100L)
set.seed(738)
stopifnot(identical(summary, summarize_archive_experiment(records[nrow(records):1, ], 100L)))
expect_error(archive_repetition_means(records[-1, ]))
expect_error(archive_repetition_means(rbind(records, records[1, ])))
expect_error(archive_repetition_means(transform(records, brier = Inf)))
expect_error(archive_repetition_means(transform(records, gain_day12_eur = 999)))
bad <- records
bad$return_day12_eur[1] <- bad$return_day12_eur[1] + 1
expect_error(archive_repetition_means(bad))
bad <- records
bad$lot_id[bad$repetition == 2L] <- sub("repeat-002", "repeat-001", bad$lot_id[bad$repetition == 2L])
expect_error(archive_repetition_means(bad))

# Hand-calculated paired block differences: +100 and -100, mean 0. Adding
# identical targets within each block adds no independent training information.
manual <- records
for (name in archive_metric_names()) manual[[name]] <- 0
manual$return_day12_eur <- 50
manual$return_day16_eur <- 50
manual$return_eur <- ifelse(manual$training_lots == 2, 200,
  ifelse(manual$repetition == 1, 300, 100))
manual$gain_day12_eur <- manual$gain_day16_eur <- manual$return_eur - 50
manual$sale_day <- 12
set.seed(739)
expected <- summarize_archive_experiment(manual, 200L)
delta <- expected$comparisons[expected$comparisons$metric == "return_eur", ]
stopifnot(delta$mean == 0, delta$lower_95 == -100, delta$upper_95 == 100,
          abs(delta$between_repetition_sd - sqrt(20000)) < 1e-10)
duplicate <- manual
duplicate$lot_id <- paste0(duplicate$lot_id, "-copy")
set.seed(739)
expanded <- summarize_archive_experiment(rbind(manual, duplicate), 200L)
stopifnot(identical(expected$summary, expanded$summary),
          identical(expected$comparisons, expanded$comparisons),
          all(expanded$repetitions$n_targets == 6L))

# Reconstruct the committed seeds, every fitted curve and all reported intervals.
path <- "results/archive_uncertainty"
settings <- dget(file.path(path, "settings.R"))
saved_seeds <- read.csv(file.path(path, "seeds.csv"))
stopifnot(identical(saved_seeds, archive_seed_manifest(settings$n_repeats, settings$master_seed)))
counts <- read.csv(file.path(path, "counts.csv"))
fits <- read.csv(file.path(path, "fits.csv"))
saved <- read.csv(file.path(path, "records.csv"))
stopifnot(nrow(saved) == 2L * settings$n_repeats * settings$n_targets,
          length(unique(saved$lot_id)) == settings$n_repeats * settings$n_targets)
for (i in seq_len(settings$n_repeats)) {
  for (size in settings$archive_sizes) {
    part <- counts[counts$repetition == i & counts$training_lots == size, ]
    rebuilt <- fit_weibull_by_cohort(part, historical_study_inventory(), settings$sensitivity, settings$specificity)
    stored <- fits[fits$repetition == i & fits$training_lots == size, names(rebuilt)]
    rownames(stored) <- NULL
    stopifnot(all(part$n_checked == size * settings$historical_checks_per_group),
              isTRUE(all.equal(rebuilt, stored, tolerance = 1e-6)))
  }
}
# Regenerate both nested archives for the first and last repetition from seeds.
for (i in c(1L, settings$n_repeats)) {
  history <- simulate_historical_inspections(max(settings$archive_sizes), saved_seeds$history_seed[i])
  for (size in settings$archive_sizes) {
    subset <- history[history$lot_id %in% head(unique(history$lot_id), size), ]
    rebuilt <- stats::aggregate(subset[c("n_checked", "n_acceptable")], subset[c("cohort", "day")], sum)
    stored <- counts[counts$repetition == i & counts$training_lots == size, names(rebuilt)]
    rownames(stored) <- NULL
    stopifnot(identical(rebuilt, stored))
  }
}
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_archive_experiment(saved, settings$n_boot)
for (name in names(rebuilt)) {
  stopifnot(isTRUE(all.equal(rebuilt[[name]], read.csv(file.path(path, paste0(name, ".csv"))), tolerance = 1e-10)))
}
cat("Orange archive uncertainty tests passed.\n")
