# Source model, sampling, evaluation, simulation, historical_baseline and
# historical_evaluation first. Base R only.

validate_archive_design <- function(n_repeats, n_targets, archive_sizes) {
  assert_nonnegative_scalar(n_repeats, "n_repeats", integer = TRUE)
  assert_nonnegative_scalar(n_targets, "n_targets", integer = TRUE)
  if (n_repeats < 2L || n_targets < 2L || !is.numeric(archive_sizes) ||
      length(archive_sizes) != 2L || any(!is.finite(archive_sizes)) ||
      any(archive_sizes != floor(archive_sizes)) || archive_sizes[1] < 2L ||
      archive_sizes[2] <= archive_sizes[1]) {
    stop("need at least two repetitions/targets and two increasing archive sizes >= 2", call. = FALSE)
  }
  invisible(TRUE)
}

archive_seed_manifest <- function(n_repeats, master_seed) {
  assert_nonnegative_scalar(n_repeats, "n_repeats", integer = TRUE)
  assert_nonnegative_scalar(master_seed, "master_seed", integer = TRUE)
  if (n_repeats < 2L) stop("need at least two repetitions", call. = FALSE)
  set.seed(master_seed)
  # Draw every stream seed before fitting; no overlapping consecutive seed ranges.
  seeds <- matrix(sample.int(.Machine$integer.max, 3L * n_repeats, replace = FALSE), ncol = 3L)
  data.frame(repetition = seq_len(n_repeats), history_seed = seeds[, 1],
    metadata_seed = seeds[, 2], fruit_seed = seeds[, 3])
}

# One independent training archive and target panel. The smaller archive is a
# prespecified prefix of the larger one; neither size is selected on target data.
run_archive_replication <- function(repetition, n_targets, archive_sizes,
                                    history_seed, metadata_seed, fruit_seed) {
  validate_archive_design(2L, n_targets, archive_sizes)
  assert_nonnegative_scalar(repetition, "repetition", integer = TRUE)
  for (field in c("history_seed", "metadata_seed", "fruit_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  history <- simulate_historical_inspections(max(archive_sizes), history_seed)
  history$lot_id <- sprintf("repeat-%03d-%s", repetition, history$lot_id)
  ids <- unique(history$lot_id)
  models <- lapply(archive_sizes, function(size) {
    fit_historical_survival(history[history$lot_id %in% head(ids, size), ],
      historical_study_inventory(), 0L, 0.9, 0.9)
  })
  # Both models are frozen before target metadata, outcomes or scores exist.
  set.seed(metadata_seed)
  targets <- lapply(seq_len(n_targets), function(id) {
    truth <- simulate_true_inventory()
    truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
    truth$mass_kg[2] <- 850 - truth$mass_kg[1]
    prices <- simulate_price_scenario(12L, 28L)
    lot_id <- sprintf("repeat-%03d-target-%03d", repetition, id)
    inventory <- transform(truth, shape = 1, scale = 1)
    days <- vapply(models, function(model) {
      historical_sale_decision(model, lot_id, inventory, prices, 0L)$sale_day
    }, numeric(1))
    fitted <- lapply(models, historical_fitted_inventory, lot_id = lot_id,
      inventory = inventory, harvest_day = 0L, decision_day = 12L)
    list(lot_id = lot_id, truth = truth, prices = prices, days = days, fitted = fitted)
  })
  # Dates for every target and both sizes precede all target fruit outcomes.
  set.seed(fruit_seed)
  records <- lapply(targets, function(lot) {
    lifetimes <- simulate_fruit_lifetimes(lot$truth)
    evaluate <- function(day) realised_sale_value(day, lot$truth, lot$prices, lifetimes, 0.001, 0L, 2L)
    day12 <- evaluate(12L)
    day16 <- evaluate(16L)
    do.call(rbind, lapply(seq_along(models), function(j) {
      forecast <- historical_forecast_records(lot$lot_id, lot$fitted[[j]], lifetimes)
      bias <- forecast$predicted_kg - forecast$accepted_kg
      value <- evaluate(lot$days[j])
      data.frame(repetition = repetition, lot_id = lot$lot_id, training_lots = archive_sizes[j],
        sale_day = lot$days[j], return_eur = value, return_day12_eur = day12, return_day16_eur = day16,
        gain_day12_eur = value - day12, gain_day16_eur = value - day16,
        brier = mean(forecast$brier), log_loss = mean(forecast$log_loss),
        bias_day16_kg = bias[1], bias_day20_kg = bias[2], bias_day24_kg = bias[3])
    }))
  })
  collect <- function(field) do.call(rbind, lapply(seq_along(models), function(j) {
    data.frame(repetition = repetition, training_lots = archive_sizes[j], models[[j]][[field]])
  }))
  list(records = do.call(rbind, records), counts = collect("counts"), fits = collect("fits"))
}

#' Compare fixed archive sizes across independent train/test repetitions.
#' @param n_repeats Independent archive/target-panel draws, at least two.
#' @param n_targets Fresh target lots per repetition, shared across archive sizes.
#' @param archive_sizes Two increasing historical-lot counts, nested per repetition.
#' @param master_seed Seed for the saved, distinct history/metadata/outcome seeds.
#' @return Target records, aggregate training counts, fits and seed manifest.
run_archive_experiment <- function(n_repeats = 30L, n_targets = 50L,
                                   archive_sizes = c(10L, 100L), master_seed = 20261117L) {
  validate_archive_design(n_repeats, n_targets, archive_sizes)
  seeds <- archive_seed_manifest(n_repeats, master_seed)
  runs <- lapply(seq_len(n_repeats), function(i) {
    tryCatch(run_archive_replication(i, n_targets, archive_sizes, seeds$history_seed[i],
      seeds$metadata_seed[i], seeds$fruit_seed[i]), error = function(error) {
        stop(sprintf("archive repetition %d: %s", i, conditionMessage(error)), call. = FALSE)
      })
  })
  collect <- function(field) do.call(rbind, lapply(runs, `[[`, field))
  list(records = collect("records"), counts = collect("counts"), fits = collect("fits"), seeds = seeds)
}

archive_metric_names <- function() c("sale_day", "return_eur", "return_day12_eur", "return_day16_eur",
  "gain_day12_eur", "gain_day16_eur", "brier", "log_loss", "bias_day16_kg", "bias_day20_kg", "bias_day24_kg")

# Collapse all paired targets before resampling: the independent unit is an
# entire training archive plus its fresh test panel, never a model/target row.
archive_repetition_means <- function(records) {
  numeric_fields <- c("repetition", "training_lots", archive_metric_names())
  if (!is.data.frame(records) || !all(c("lot_id", numeric_fields) %in% names(records)) ||
      !is.character(records$lot_id) || anyNA(records$lot_id) || any(!nzchar(trimws(records$lot_id))) ||
      any(!vapply(records[numeric_fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1)))) {
    stop("archive records need identified targets and finite numeric measurements", call. = FALSE)
  }
  sizes <- sort(unique(records$training_lots))
  repeats <- sort(unique(records$repetition))
  validate_archive_design(length(repeats), 2L, sizes)
  if (any(repeats < 1 | repeats != floor(repeats)) ||
      anyDuplicated(records[c("repetition", "lot_id", "training_lots")])) {
    stop("each target/size needs one record in an identified repetition", call. = FALSE)
  }
  panels <- split(records, records$repetition)
  counts <- vapply(panels, function(part) length(unique(part$lot_id)), integer(1))
  if (length(unique(counts)) != 1L || any(counts < 2L) ||
      length(unique(records$lot_id)) != sum(counts)) {
    stop("repetitions need equally sized, disjoint target panels with at least two lots", call. = FALSE)
  }
  for (part in panels) {
    if (!setequal(part$training_lots, sizes) || any(table(part$lot_id, part$training_lots) != 1L)) {
      stop("both archive sizes must evaluate every target exactly once", call. = FALSE)
    }
    small <- part[part$training_lots == sizes[1], ]
    large <- part[part$training_lots == sizes[2], ]
    large <- large[match(small$lot_id, large$lot_id), ]
    if (any(small$return_day12_eur != large$return_day12_eur) ||
        any(small$return_day16_eur != large$return_day16_eur)) {
      stop("fixed-date returns must be paired across archive sizes", call. = FALSE)
    }
  }
  if (any(abs(records$gain_day12_eur - (records$return_eur - records$return_day12_eur)) > 1e-8) ||
      any(abs(records$gain_day16_eur - (records$return_eur - records$return_day16_eur)) > 1e-8)) {
    stop("saved return gains must match their fixed-date contrasts", call. = FALSE)
  }
  records <- records[order(records$repetition, records$training_lots, records$lot_id), ]
  result <- stats::aggregate(records[archive_metric_names()],
    records[c("repetition", "training_lots")], mean)
  result$n_targets <- unname(counts[as.character(result$repetition)])
  result[order(result$repetition, result$training_lots), ]
}

#' Percentile intervals for expected performance over new training/test draws.
#' Both policies are paired within each resampled repetition. Scores average
#' equally over future days 16/20/24 within a target, then over targets/blocks.
#' @return Repetition means, per-size metric intervals, large-minus-small intervals.
summarize_archive_experiment <- function(records, n_boot = 2000L) {
  blocks <- archive_repetition_means(records)
  sizes <- sort(unique(blocks$training_lots))
  metrics <- c("return_eur", "gain_day12_eur", "gain_day16_eur", "brier", "log_loss",
    "bias_day16_kg", "bias_day20_kg", "bias_day24_kg")
  summarize <- function(values) {
    # The existing mean bootstrap helper operates on independent BLOCK means.
    ci <- paired_lot_interval(values, n_boot)
    data.frame(n_repeats = length(values), mean = unname(ci["mean"]),
      lower_95 = unname(ci["lower_95"]), upper_95 = unname(ci["upper_95"]),
      between_repetition_sd = stats::sd(values))
  }
  per_size <- do.call(rbind, lapply(sizes, function(size) {
    part <- blocks[blocks$training_lots == size, ]
    do.call(rbind, lapply(metrics, function(metric) {
      data.frame(training_lots = size, metric = metric, summarize(part[[metric]]))
    }))
  }))
  small <- blocks[blocks$training_lots == sizes[1], ]
  large <- blocks[blocks$training_lots == sizes[2], ]
  stopifnot(identical(small$repetition, large$repetition))
  differences <- do.call(rbind, lapply(metrics, function(metric) {
    data.frame(smaller_archive = sizes[1], larger_archive = sizes[2], metric = metric,
      summarize(large[[metric]] - small[[metric]]))
  }))
  rownames(blocks) <- rownames(per_size) <- rownames(differences) <- NULL
  list(repetitions = blocks, summary = per_size, comparisons = differences)
}
