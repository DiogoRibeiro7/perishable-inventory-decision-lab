# Run from studies/orange_storage_decision:
# Rscript scripts/run_archive_uncertainty.R [repetitions] [output_directory] [targets_per_repetition]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 3L) stop("usage: run_archive_uncertainty.R [repetitions] [output_directory] [targets_per_repetition]")
n_repeats <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 30L
destination <- if (length(args) >= 2L) args[2] else "results/archive_uncertainty"
n_targets <- if (length(args) == 3L) suppressWarnings(as.numeric(args[3])) else 50L
settings <- list(n_repeats = n_repeats, n_targets = n_targets, archive_sizes = c(10L, 100L),
  master_seed = 20261117L, bootstrap_seed = 9217L, n_boot = 2000L,
  fit_calendar_day = 0L, target_harvest_day = 0L,
  historical_days = c(4L, 8L, 12L, 16L, 20L, 24L), historical_checks_per_group = 60L,
  sensitivity = 0.9, specificity = 0.9, decision_day = 12L, last_sale_day = 28L,
  forecast_days = c(16L, 20L, 24L), delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, fruit_mass_kg = 0.20,
  resampling_unit = "independent training archive plus target panel",
  r_version = R.version.string, rng_kind = RNGkind())
result <- run_archive_experiment(n_repeats, n_targets, settings$archive_sizes, settings$master_seed)
set.seed(settings$bootstrap_seed)
estimates <- summarize_archive_experiment(result$records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
tables <- c(result, estimates)
for (name in names(tables)) utils::write.csv(tables[[name]], file.path(destination, paste0(name, ".csv")), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"), file.path(destination, "settings.R"), useBytes = TRUE)

labels <- c(return_eur = "Return (EUR/lot)", gain_day12_eur = "Gain vs day 12 (EUR/lot)",
  gain_day16_eur = "Gain vs day 16 (EUR/lot)", brier = "Brier score", log_loss = "Log loss",
  bias_day16_kg = "Day 16 inventory bias (kg)", bias_day20_kg = "Day 20 inventory bias (kg)",
  bias_day24_kg = "Day 24 inventory bias (kg)")
lines <- c("# Uncertainty across historical training archives", "",
  sprintf("%d independent train/test repetitions, each with %d fresh target lots.", n_repeats, n_targets),
  "Each repetition fits models on 10 and 100 historical lots; the smaller",
  "archive is the first 10 lots of the larger archive. Both frozen policies",
  "evaluate the same target fruit and price paths, without target inspections.",
  sprintf("There are %d unique target lots and %d paired policy/target records.",
    n_repeats * n_targets, nrow(result$records)), "",
  "## Expected deployment performance", "",
  "Intervals resample entire train/test repetitions, including archive variation.",
  "They describe the mean of the training-and-deployment procedure under the",
  "fixed synthetic regime, not the performance range of a particular archive",
  "or an individual target lot. No target row is resampled independently.", "",
  "| Metric | Historical lots | Mean [95% CI] | SD across repetition means |",
  "|---|---:|---:|---:|")
for (metric in names(labels)) {
  for (size in settings$archive_sizes) {
    x <- estimates$summary[estimates$summary$metric == metric & estimates$summary$training_lots == size, ]
    digits <- if (metric %in% c("brier", "log_loss")) 5L else 2L
    lines <- c(lines, sprintf("| %s | %d | %.*f [%.*f, %.*f] | %.*f |", labels[metric], size,
      digits, x$mean, digits, x$lower_95, digits, x$upper_95, digits, x$between_repetition_sd))
  }
}
lines <- c(lines, "", "## Paired effect of using 100 instead of 10 historical lots", "",
  "All contrasts are **100 minus 10**. Positive return differences favour the",
  "larger archive; negative Brier/log-loss differences favour it. Signed bias",
  "differences are not improvements by themselves: zero absolute bias is ideal.", "",
  "| Metric | Paired mean difference [95% CI] |",
  "|---|---:|")
for (i in seq_len(nrow(estimates$comparisons))) {
  x <- estimates$comparisons[i, ]
  digits <- if (x$metric %in% c("brier", "log_loss")) 5L else 2L
  lines <- c(lines, sprintf("| %s | %.*f [%.*f, %.*f] |", labels[x$metric],
    digits, x$mean, digits, x$lower_95, digits, x$upper_95))
}
lines <- c(lines, "", "![Variation across training archives](archive_uncertainty.png)", "",
  "## Scope and reproduction", "",
  "Each archive has six ages, two strata and 60 checks per stratum/age/lot:",
  "7,200 checks for 10 lots versus 72,000 for 100. Known grading sensitivity",
  "and specificity are both 0.90. Training is complete before target harvest;",
  "all target sale dates are fixed before target fruit outcomes are generated.", "",
  "Every target retains 850 kg of initially eligible fruit. Returns include",
  "holding from harvest through delivery, at EUR 0.001/kg/day with a two-day",
  "delivery lag and known supplied prices. Fixed-date comparators retain the",
  "same fruit. Archive collection, destructive losses, labour and model-development",
  "costs are excluded; this is not an economic recommendation to buy more data.", "",
  "Brier/log loss use individual-fruit outcomes and initial mass weights, then",
  "average equally across ages 16, 20 and 24 and target lots. Inventory bias is",
  "predicted minus observed acceptable kg. Repeated future scores stay within",
  "their target and repetition. Standard deviations mix training variation with",
  "finite-target-panel variation; this study does not separate those components.", "",
  "The working marginal Weibull family and both archive sizes were fixed before",
  "evaluation. More data cannot remove its possible misspecification. History",
  "and targets share one synthetic regime; field validation, distribution shift,",
  "uncertain grading accuracy and uncertain prices remain open. The percentile",
  "95% intervals are marginal, based on 2,000 repetition resamples, without",
  "multiplicity correction. The number of independent units is the repetition",
  "count, not the number of target fruit or policy records.", "",
  "```sh", sprintf("Rscript scripts/run_archive_uncertainty.R %d results/archive_uncertainty %d", n_repeats, n_targets),
  "```", "",
  "[Seeds](seeds.csv) reconstruct every full historical archive and fresh target",
  "panel. [Aggregated training counts](counts.csv) are sufficient to reconstruct",
  "the [fitted curves](fits.csv); they are not the individual historical-lot data.",
  "[Target records](records.csv), [repetition means](repetitions.csv),",
  "[performance intervals](summary.csv), [paired contrasts](comparisons.csv) and",
  "[settings](settings.R) preserve the calculations. See",
  "[ARCHIVE_UNCERTAINTY.md](../../ARCHIVE_UNCERTAINTY.md) for the protocol and API.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "archive_uncertainty.png"), width = 1500, height = 820, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 5, 4, 1), mgp = c(3.4, 1, 0))
blocks <- estimates$repetitions
small <- blocks[blocks$training_lots == 10L, ]
large <- blocks[blocks$training_lots == 100L, ]
panels <- list(list(metric = "gain_day12_eur", title = "Gain over fixed sale on day 12",
    ylab = "Mean return advantage per target lot (EUR)"),
  list(metric = "brier", title = "Future prediction error", ylab = "Mean individual-fruit Brier score"))
for (panel in panels) {
  metric <- panel$metric
  x <- estimates$summary[estimates$summary$metric == metric, ]
  limits <- range(c(small[[metric]], large[[metric]], x$lower_95, x$upper_95))
  if (metric == "gain_day12_eur") limits <- range(c(0, limits))
  graphics::plot(NA, xlim = c(0.7, 2.3), ylim = limits, xaxt = "n", las = 1,
    xlab = "Historical training lots", ylab = panel$ylab, main = panel$title)
  graphics::mtext("Grey: paired repetitions; blue: mean and 95% CI", side = 3, line = 0.4, cex = 0.7)
  graphics::segments(1, small[[metric]], 2, large[[metric]], col = "grey75")
  graphics::points(rep(1:2, each = n_repeats), c(small[[metric]], large[[metric]]), pch = 16, cex = 0.5, col = "grey60")
  if (metric == "gain_day12_eur") graphics::abline(h = 0, lty = 2, col = "grey50")
  graphics::arrows(1:2, x$lower_95, 1:2, x$upper_95, code = 3, angle = 90, length = 0.07, col = "#276a98", lwd = 2)
  graphics::points(1:2, x$mean, pch = 19, col = "#276a98", cex = 1.3)
  graphics::axis(1, at = 1:2, labels = c("10", "100"))
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d independent train/test repetitions to %s\n", n_repeats, destination))
