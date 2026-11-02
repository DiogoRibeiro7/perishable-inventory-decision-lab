# Run from studies/orange_storage_decision:
# Rscript scripts/run_historical_baseline.R [number_of_target_lots] [output_directory]
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

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_historical_baseline.R [number_of_target_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/historical_baseline"
settings <- list(n_lots = n_lots, n_history = 100L, history_seed = 20261113L,
  metadata_seed = 20261114L, fruit_seed = 20261115L, sampling_seed = 20261116L,
  bootstrap_seed = 9216L, n_boot = 1000L, fit_calendar_day = 0L, target_harvest_day = 0L,
  historical_days = c(4L, 8L, 12L, 16L, 20L, 24L), historical_checks_per_group = 60L,
  target_inspection_budgets = c(30L, 180L), target_inspection_days = c(3L, 6L, 9L, 12L),
  inspection_labour_eur = 0.02, sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, fruit_mass_kg = 0.20,
  r_version = R.version.string, rng_kind = RNGkind())
result <- run_historical_experiment(n_lots, settings$n_history, settings$history_seed,
  settings$metadata_seed, settings$fruit_seed, settings$sampling_seed)
set.seed(settings$bootstrap_seed)
returns <- summarize_historical_returns(result$records, settings$n_boot)
forecasts <- summarize_historical_forecasts(result$forecasts, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
tables <- list(history = result$history, fits = result$model$fits, records = result$records,
  forecasts = result$forecasts, return_summary = returns, forecast_summary = forecasts)
for (name in names(tables)) utils::write.csv(tables[[name]], file.path(destination, paste0(name, ".csv")), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"), file.path(destination, "settings.R"), useBytes = TRUE)

labels <- c("No inspection, day 12", "No inspection, day 16", "Destructive, 30/stratum/day", "Destructive, 180/stratum/day")
lines <- c("# A frozen historical survival baseline", "",
  sprintf("Fit once on %d independent historical lots; evaluate on %d fresh target lots without refitting or tuning.", settings$n_history, n_lots),
  "The historical policy uses initial grade masses and the supplied price path,",
  "retains all 850 kg of eligible target fruit and performs no target inspections.",
  "The archive contains 72,000 reported checks, with known sensitivity/specificity",
  "of 0.90. All archive observations were available before the target harvest.", "",
  sprintf("The frozen policy sells on mean day %.2f and earns mean EUR %.2f per target lot.",
    returns$mean_historical_sale_day[1], returns$mean_historical_return_eur[1]), "",
  "## Paired target-lot returns", "",
  "All returns include eligible holding costs from harvest through delivery.",
  "Destructive comparators pay EUR 0.02 per check and lose the actual sampled",
  "fruit; the historical and fixed-date policies keep the full population.", "",
  "| Comparator | Mean comparator EUR | Historical minus comparator EUR [95% CI] | Historical below comparator |",
  "|---|---:|---:|---:|")
for (i in seq_len(nrow(returns))) {
  x <- returns[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %+.2f [%+.2f, %+.2f] | %.1f%% |", labels[i],
    x$mean_comparator_return_eur, x$gain_mean_eur, x$gain_lower_95_eur, x$gain_upper_95_eur,
    100 * x$below_comparator_fraction))
}
lines <- c(lines, "", "## Future inventory forecasts", "",
  "Predictions concern true acceptance, not noisy grading labels. Scores use",
  "individual-fruit Brier/log loss, standardised to initial eligible inventory.",
  "The same uninspected target fruit are assessed on each future day; intervals",
  "resample whole target lots and do not treat repeated assessments as independent.", "",
  "| Fruit age | Predicted kg | Observed acceptable kg | Bias kg [95% CI] | Brier | Log loss |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(forecasts))) {
  x <- forecasts[i, ]
  lines <- c(lines, sprintf("| %d | %.2f | %.2f | %+.2f [%+.2f, %+.2f] | %.4f | %.4f |", x$day,
    x$mean_predicted_kg, x$mean_accepted_kg, x$bias_mean_kg, x$bias_lower_95_kg,
    x$bias_upper_95_kg, x$mean_brier, x$mean_log_loss))
}
lines <- c(lines, "", "![Historical baseline evaluation](historical_baseline.png)", "",
  "## Interpretation and reproduction", "",
  "This is a working marginal Weibull fit per stratum, not a hierarchical model",
  "or an estimate of a particular target lot's latent deterioration curve.",
  "Historical and target lots share the same synthetic generating regime.",
  "Historical IDs and calendar availability are checked; all historical-policy",
  "dates are fixed before target fruit outcomes are generated.", "",
  "The archive is assumed already available. Its collection, destructive losses,",
  "labour and model-development costs are excluded. These deployment comparisons",
  "do not establish whether acquiring this archive pays for itself. Predictive",
  "and return intervals condition on this one frozen archive; uncertainty across",
  "alternative training archives and distribution shifts is not included.", "",
  "Return contrasts against destructive plans combine timing and physical",
  "sampling costs; they do not establish superior predictive accuracy over",
  "per-lot fits. Positive returns can coexist with biased inventory forecasts.", "",
  "All intervals are marginal whole-lot percentile 95% intervals, without",
  "multiple-comparison adjustment. Aggregate inventory bias does not establish",
  "stratum-specific calibration or field performance. Prices and grading accuracy",
  "are assumed known; handling damage, dependence and real operational costs",
  "remain outside the model. No model or policy was selected using these targets.", "",
  "```sh", sprintf("Rscript scripts/run_historical_baseline.R %d", n_lots), "```", "",
  "[Historical counts](history.csv), [fitted curves](fits.csv), [paired returns](records.csv),",
  "[future measurements](forecasts.csv), [return summary](return_summary.csv),",
  "[forecast summary](forecast_summary.csv) and [settings](settings.R) preserve the evidence.",
  "See [HISTORICAL_BASELINE.md](../../HISTORICAL_BASELINE.md) for the data contract and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "historical_baseline.png"), width = 1500, height = 820, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(6, 5, 4, 1), mgp = c(3.5, 1, 0))
graphics::plot(1:4, returns$gain_mean_eur, pch = 19, col = "#276a98", xaxt = "n", las = 1,
  xlim = c(0.6, 4.4), ylim = range(c(0, returns$gain_lower_95_eur, returns$gain_upper_95_eur)),
  xlab = "", ylab = "Mean historical-policy advantage (EUR/lot)", main = "Deployment returns")
graphics::mtext("95% intervals conditional on this training archive", side = 3, line = 0.4, cex = 0.7)
graphics::axis(1, at = 1:4, labels = c("No checks\nday 12", "No checks\nday 16", "30 checks\n/stratum/day", "180 checks\n/stratum/day"), cex.axis = 0.75)
graphics::abline(h = 0, lty = 2, col = "grey50")
graphics::arrows(1:4, returns$gain_lower_95_eur, 1:4, returns$gain_upper_95_eur,
  code = 3, angle = 90, length = 0.06, col = "#276a98")
graphics::plot(forecasts$day, forecasts$bias_mean_kg, pch = 19, col = "#276a98", xaxt = "n", las = 1,
  ylim = range(c(0, forecasts$bias_lower_95_kg, forecasts$bias_upper_95_kg)),
  xlab = "Future fruit age (days)", ylab = "Mean predicted minus observed mass (kg)", main = "Inventory forecast bias")
graphics::mtext("Paired whole-target-lot 95% bootstrap intervals", side = 3, line = 0.4, cex = 0.7)
graphics::axis(1, at = forecasts$day)
graphics::abline(h = 0, lty = 2, col = "grey50")
graphics::arrows(forecasts$day, forecasts$bias_lower_95_kg, forecasts$day, forecasts$bias_upper_95_kg,
  code = 3, angle = 90, length = 0.06, col = "#276a98")
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d target-lot records to %s\n", nrow(result$records), destination))
