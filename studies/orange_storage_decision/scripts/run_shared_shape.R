# Run from studies/orange_storage_decision:
# Rscript scripts/run_shared_shape.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_shared_shape.R [number_of_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/shared_shape"
settings <- list(n_lots = n_lots, training_seed = 20261102L, outcome_seed = 20261103L,
  bootstrap_seed = 9211L, n_boot = 1000L, sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, training_per_group = 180L, holdout_per_group = 250L,
  scenarios = default_shape_scenarios(), r_version = R.version.string, rng_kind = RNGkind())
records <- run_shared_shape_experiment(n_lots, settings$training_seed,
  settings$outcome_seed, settings$scenarios)
set.seed(settings$bootstrap_seed)
summary <- summarize_shared_shape(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
  file.path(destination, "settings.R"), useBytes = TRUE)
lines <- c("# Sharing Weibull shape across fruit strata: synthetic comparison", "",
  sprintf("%d independent lots per scenario, paired across fitted models and generating scenarios.", n_lots),
  "Both fits receive the same noisy day-3/6/9/12 inspections and exact 90%",
  "sensitivity/specificity. Future scores use gold-standard inspections.",
  "Shared shape retains separate stratum scales; separate fitting estimates both",
  "parameters independently. All decisions precede future outcome generation.", "",
  "## Future prediction quality", "",
  "Lower scores are better. Improvement is separate minus shared; intervals are",
  "paired whole-lot bootstrap intervals for mean differences.", "",
  "| Generating scenario | Separate Brier | Shared Brier | Improvement [95% CI] | Separate log loss | Shared log loss |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.4f | %.4f | %+.4f [%+.4f, %+.4f] | %.4f | %.4f |",
    x$scenario, x$mean_brier_separate, x$mean_brier_shared, x$brier_improvement_mean,
    x$brier_improvement_lower_95, x$brier_improvement_upper_95,
    x$mean_log_loss_separate, x$mean_log_loss_shared))
}
lines <- c(lines, "", "## Realised return per initially eligible 850-kg lot", "",
  "Returns are EUR after storage and delivery rejection, under perfectly known prices.", "",
  "| Scenario | Separate | Shared | Immediate | Shared - separate [95% CI] | Shared - immediate [95% CI] |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.2f | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] |",
    x$scenario, x$mean_realised_separate_eur, x$mean_realised_shared_eur,
    x$mean_realised_immediate_eur, x$shared_minus_separate_eur_mean,
    x$shared_minus_separate_eur_lower_95, x$shared_minus_separate_eur_upper_95,
    x$shared_minus_immediate_eur_mean, x$shared_minus_immediate_eur_lower_95,
    x$shared_minus_immediate_eur_upper_95))
}
lines <- c(lines, "", "## Decisions and descriptive downside", "",
  "| Scenario | Separate mean day | Shared mean day | Different dates | Separate below immediate | Shared below immediate |",
  "|---|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.1f%% | %.1f%% | %.1f%% |", x$scenario,
    x$mean_sale_day_separate, x$mean_sale_day_shared, 100 * x$different_sale_day_fraction,
    100 * x$separate_below_immediate_fraction, 100 * x$shared_below_immediate_fraction))
}
stress <- summary[summary$scenario == "different_shapes", ]
lines <- c(lines, "", "![Predictive and economic effects](shared_shape.png)", "",
  "## Interpretation and reproduction", "",
  sprintf("Shared shape improves mean Brier scores in %d of %d regimes.",
    sum(summary$brier_improvement_mean > 0), nrow(summary)),
  sprintf("With different shapes, its return difference is EUR %+.2f [%.2f, %.2f],",
    stress$shared_minus_separate_eur_mean, stress$shared_minus_separate_eur_lower_95,
    stress$shared_minus_separate_eur_upper_95),
  sprintf("and observed underperformance against immediate sale is %.1f%% versus %.1f%% for separate fits.",
    100 * stress$shared_below_immediate_fraction, 100 * stress$separate_below_immediate_fraction),
  "Prediction quality and the economic consequences of a chosen date are distinct.", "",
  "A common shape imposes a structural restriction. It can reduce estimation",
  "variation but introduce bias when strata have different deterioration shapes.",
  "This comparison does not select a model using the future scores. Negative",
  "effects are retained, including under the deliberately different-shape regime.", "",
  "Intervals are marginal without multiplicity adjustment. Downside fractions are",
  "descriptive and exclude ties. Exact calibration, independent samples, Weibull",
  "deterioration, negligible inspection removals and known prices are assumptions.",
  "Calibration uncertainty and storage shocks are not combined with this experiment.",
  "Synthetic comparisons do not establish field profitability or model validity.", "",
  "```sh", sprintf("Rscript scripts/run_shared_shape.R %d", n_lots), "```", "",
  "[Paired records](records.csv), [summary](summary.csv) and [settings](settings.R)",
  "preserve the results. See [SHARED_SHAPE.md](../../SHARED_SHAPE.md) for the model and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "shared_shape.png"), width = 1500, height = 780, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 4.5, 4, 1))
labels <- c("Equal\nshapes", "Nearby\nshapes", "Different\nshapes")
contrasts <- c("brier_improvement", "shared_minus_separate_eur")
for (i in seq_along(contrasts)) {
  prefix <- contrasts[i]
  means <- summary[[paste0(prefix, "_mean")]]
  lower <- summary[[paste0(prefix, "_lower_95")]]
  upper <- summary[[paste0(prefix, "_upper_95")]]
  x <- seq_along(means)
  graphics::plot(x, means, pch = 19, col = "#276a98", xaxt = "n", las = 1,
    ylim = range(c(0, lower, upper)), xlab = "",
    ylab = c("Separate minus shared Brier score", "Shared minus separate return (EUR per lot)")[i],
    main = c("Future prediction improvement", "Realised return difference")[i])
  graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  nonzero <- upper > lower
  graphics::arrows(x[nonzero], lower[nonzero], x[nonzero], upper[nonzero],
    angle = 90, code = 3, length = 0.05, col = "#276a98")
  graphics::axis(1, x, labels, cex.axis = 0.9)
}
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d paired records to %s\n", nrow(records), destination))
