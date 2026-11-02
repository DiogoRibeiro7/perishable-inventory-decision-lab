# Run from studies/orange_storage_decision:
# Rscript scripts/run_inspection_error.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/inspection_error.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) {
  stop("usage: Rscript scripts/run_inspection_error.R [number_of_lots] [output_directory]",
       call. = FALSE)
}
n_lots <- if (length(args) >= 1L) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) >= 2L) args[2] else "results/inspection_error"
settings <- list(n_lots = n_lots, simulation_seed = 20261028L, label_seed = 20261029L,
                 outcome_seed = 20261030L, bootstrap_seed = 9190L, n_boot = 1000L,
                 decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
                 storage_eur_per_kg_day = 0.001, training_per_group = 180L,
                 holdout_per_group = 250L, scenarios = default_inspection_scenarios(),
                 r_version = R.version.string, rng_kind = RNGkind())
records <- run_inspection_error_experiment(n_lots, settings$simulation_seed,
  settings$label_seed, settings$outcome_seed, settings$scenarios)
set.seed(settings$bootstrap_seed)
summary <- summarize_inspection_error(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
            file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c(
  "# Correcting inspection errors: synthetic evaluation", "",
  sprintf("%d independent lots; naive and corrected fits see the same noisy training labels.", n_lots),
  "The corrected fit is supplied the true sensitivity and specificity as if",
  "known from external calibration. These are assumed rates, not measured data.",
  "Gold-standard future inspections and fruit outcomes are shared by all policies.", "",
  "## Future prediction quality", "",
  "Brier and log loss score true acceptance, not reported labels. Lower is better.",
  "Brier improvement is naive minus corrected, with a paired lot-bootstrap interval.", "",
  "| Scenario | Sensitivity | Specificity | Naive Brier | Corrected Brier | Brier improvement [95% CI] | Naive log loss | Corrected log loss |",
  "|---|---:|---:|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  setting <- settings$scenarios[settings$scenarios$scenario == x$scenario, ]
  lines <- c(lines, sprintf(
    "| %s | %.2f | %.2f | %.4f | %.4f | %+.4f [%+.4f, %+.4f] | %.4f | %.4f |",
    x$scenario, setting$sensitivity, setting$specificity,
    x$mean_brier_naive, x$mean_brier_corrected, x$brier_improvement_mean,
    x$brier_improvement_lower_95, x$brier_improvement_upper_95,
    x$mean_log_loss_naive, x$mean_log_loss_corrected))
}
lines <- c(lines, "", "## Mean realised net return per initially eligible 850-kg lot", "",
  "Values are EUR after storage and delivery rejection. Economic improvements",
  "are measured separately from predictive improvements.", "",
  "| Scenario | Naive | Corrected | Immediate | Corrected - naive [95% CI] | Corrected - immediate [95% CI] |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf(
    "| %s | %.2f | %.2f | %.2f | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] |",
    x$scenario, x$mean_realised_naive_eur, x$mean_realised_corrected_eur,
    x$mean_realised_immediate_eur, x$corrected_minus_naive_eur_mean,
    x$corrected_minus_naive_eur_lower_95, x$corrected_minus_naive_eur_upper_95,
    x$corrected_minus_immediate_eur_mean, x$corrected_minus_immediate_eur_lower_95,
    x$corrected_minus_immediate_eur_upper_95))
}
lines <- c(lines, "", "## Decisions and descriptive downside", "",
  "Strict underperformance excludes exact ties. Fractions are descriptive.", "",
  "| Scenario | Naive mean sale day | Corrected mean sale day | Different dates | Naive below immediate | Corrected below immediate |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.1f%% | %.1f%% | %.1f%% |", x$scenario,
    x$mean_sale_day_naive, x$mean_sale_day_corrected, 100 * x$different_sale_day_fraction,
    100 * x$naive_below_immediate_fraction, 100 * x$corrected_below_immediate_fraction))
}
noisy <- summary[summary$scenario != "perfect", ]
lines <- c(lines, "", "![Prediction and decision effects](inspection_error.png)", "",
  "## Interpretation and reproduction", "",
  sprintf("Correction increases mean returns versus naive fitting in %d of %d noisy scenarios,",
    sum(noisy$corrected_minus_naive_eur_mean > 0), nrow(noisy)),
  sprintf("but worsens mean future Brier scores in %d and mean log loss in %d of them.",
    sum(noisy$brier_improvement_mean < 0), sum(noisy$log_loss_improvement_mean < 0)),
  sprintf("Corrected-minus-immediate return intervals include zero in %d of %d noisy scenarios.",
    sum(noisy$corrected_minus_immediate_eur_lower_95 <= 0 &
          noisy$corrected_minus_immediate_eur_upper_95 >= 0), nrow(noisy)),
  "Short, noisy training histories can yield unstable survival extrapolations",
  "even under a correctly specified measurement model. Fixed calibration does",
  "not restore information lost through misclassification.", "",
  "Intervals are marginal and do not adjust for multiple comparisons. The",
  "correction assumes exact, stable calibration rates shared by strata/days.",
  "Calibration uncertainty, correlated inspection mistakes and imperfect future",
  "reference labels are not simulated. Weibull deterioration and perfectly known",
  "prices remain assumptions. These results do not establish field profitability.", "",
  "From the project folder:", "", "```sh",
  sprintf("Rscript scripts/run_inspection_error.R %d", n_lots), "```", "",
  "[records.csv](records.csv), [summary.csv](summary.csv) and [settings.R](settings.R)",
  "contain paired measurements, all metrics and reproduction settings.",
  "See [INSPECTION_ERROR.md](../../INSPECTION_ERROR.md) for the likelihood and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "inspection_error.png"), width = 1500, height = 780, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 4.5, 4, 1))
x <- seq_len(nrow(summary))
labels <- c("Perfect", "Balanced\nerrors", "More false\naccepts", "More false\nrejects")
contrasts <- c("brier_improvement", "corrected_minus_naive_eur")
for (i in seq_along(contrasts)) {
  prefix <- contrasts[i]
  means <- summary[[paste0(prefix, "_mean")]]
  lower <- summary[[paste0(prefix, "_lower_95")]]
  upper <- summary[[paste0(prefix, "_upper_95")]]
  graphics::plot(x, means, pch = 19, col = "#276a98", xaxt = "n", las = 1,
    ylim = range(c(0, lower, upper)), xlab = "",
    ylab = c("Naive minus corrected Brier score", "Corrected minus naive return (EUR per lot)")[i],
    main = c("Future prediction improvement", "Realised return difference")[i])
  graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  nonzero <- upper > lower
  graphics::arrows(x[nonzero], lower[nonzero], x[nonzero], upper[nonzero],
                    angle = 90, code = 3, length = 0.05, col = "#276a98")
  graphics::axis(1, x, labels, cex.axis = 0.85)
}
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d paired records to %s\n", nrow(records), destination))
