# Run from studies/orange_storage_decision:
# Rscript scripts/run_shape_ensemble.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_shape_ensemble.R [number_of_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/shape_ensemble"
settings <- list(n_lots = n_lots, training_seed = 20261104L, outcome_seed = 20261105L,
  bootstrap_seed = 9212L, n_boot = 1000L, sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, training_per_group = 180L, holdout_per_group = 250L,
  weighting = "normalised exp(-0.5 * delta AIC) on reported training counts",
  separate_fit = "retry from shared solution when a stratum loss is worse by more than 1e-8",
  parameters = c(separate = 4L, shared = 3L), scenarios = default_shape_scenarios(),
  r_version = R.version.string, rng_kind = RNGkind())
records <- run_shape_ensemble_experiment(n_lots, settings$training_seed,
  settings$outcome_seed, settings$scenarios)
set.seed(settings$bootstrap_seed)
summary <- summarize_shape_ensemble(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
  file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c("# Averaging separate and shared Weibull shapes: synthetic comparison", "",
  sprintf("%d independent base lots, each evaluated under three paired generating scenarios.", n_lots),
  "Weights use AIC from the same noisy day-3/6/9/12 inspections, with exact",
  "90% sensitivity/specificity. The mixture averages survival probabilities",
  "and selects the earliest maximum of its expected net-value curve.",
  "All weights and sale dates are fixed before future outcomes are generated.", "",
  "Separate component fits retry from feasible shared-shape solutions when needed.",
  "The separate benchmark uses those same refined fits; previous studies are unchanged.", "",
  "## Training weights and future prediction quality", "",
  "Lower Brier and log loss are better. Weights are descriptive model weights,",
  "not calibrated probabilities that a generating model is true.", "",
  "| Scenario | Mean shared weight | Separate Brier | Shared Brier | Ensemble Brier | Separate log loss | Shared log loss | Ensemble log loss |",
  "|---|---:|---:|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.3f | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f |",
    x$scenario, x$mean_ensemble_weight_shared, x$mean_brier_separate, x$mean_brier_shared,
    x$mean_brier_ensemble, x$mean_log_loss_separate, x$mean_log_loss_shared, x$mean_log_loss_ensemble))
}
lines <- c(lines, "", "## Realised return per initially eligible 850-kg lot", "",
  "Returns are EUR after storage and delivery rejection, under perfectly known prices.", "",
  "| Scenario | Separate | Shared | Ensemble | Immediate |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.2f | %.2f |", x$scenario,
    x$mean_realised_separate_eur, x$mean_realised_shared_eur, x$mean_realised_ensemble_eur,
    x$mean_realised_immediate_eur))
}
lines <- c(lines, "", "Paired mean differences with marginal 95% whole-lot bootstrap intervals:", "",
  "| Scenario | Ensemble - separate | Ensemble - shared | Ensemble - immediate |",
  "|---|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] |",
    x$scenario, x$ensemble_minus_separate_eur_mean, x$ensemble_minus_separate_eur_lower_95,
    x$ensemble_minus_separate_eur_upper_95, x$ensemble_minus_shared_eur_mean,
    x$ensemble_minus_shared_eur_lower_95, x$ensemble_minus_shared_eur_upper_95,
    x$ensemble_minus_immediate_eur_mean, x$ensemble_minus_immediate_eur_lower_95,
    x$ensemble_minus_immediate_eur_upper_95))
}
lines <- c(lines, "", "## Decisions and descriptive downside", "",
  "Fractions use all lots as the denominator; only strictly lower returns count as losses.", "",
  "| Scenario | Separate mean day | Shared mean day | Ensemble mean day | Separate below immediate | Shared below immediate | Ensemble below immediate |",
  "|---|---:|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.2f | %.1f%% | %.1f%% | %.1f%% |", x$scenario,
    x$mean_sale_day_separate, x$mean_sale_day_shared, x$mean_sale_day_ensemble,
    100 * x$separate_below_immediate_fraction, 100 * x$shared_below_immediate_fraction,
    100 * x$ensemble_below_immediate_fraction))
}
stress <- summary[summary$scenario == "different_shapes", ]
lines <- c(lines, "", "![Ensemble effects relative to shared shape](shape_ensemble.png)", "",
  "## Interpretation and reproduction", "",
  sprintf("The ensemble has lower mean Brier scores than separate fits in %d of %d regimes,",
    sum(summary$brier_improvement_vs_separate_mean > 0), nrow(summary)),
  sprintf("and lower scores than shared shape in %d of %d regimes.",
    sum(summary$brier_improvement_vs_shared_mean > 0), nrow(summary)),
  sprintf("With different shapes, its return difference from shared shape is EUR %+.2f [%.2f, %.2f],",
    stress$ensemble_minus_shared_eur_mean, stress$ensemble_minus_shared_eur_lower_95,
    stress$ensemble_minus_shared_eur_upper_95),
  sprintf("and observed underperformance against immediate sale is %.1f%%, versus %.1f%% for shared and %.1f%% for separate fits.",
    100 * stress$ensemble_below_immediate_fraction, 100 * stress$shared_below_immediate_fraction,
    100 * stress$separate_below_immediate_fraction),
  "Better average prediction does not guarantee better decisions or lower downside.", "",
  "AIC weights are fixed from the training likelihood, not tuned on future scores.",
  "Short histories, weak identification and bounded optimisation limit the usual",
  "AIC approximation. Averaging does not guarantee improvement over either component.",
  "Intervals are marginal without multiplicity adjustment; downside is descriptive.",
  "The three regimes share base lots and are not pooled as independent observations.", "",
  "Exact calibration, independent inspections, Weibull deterioration within strata,",
  "negligible sampling removals and known prices are assumptions. Calibration",
  "uncertainty and storage shocks are not combined here. These synthetic results",
  "do not establish field profitability or empirical model validity.", "",
  "```sh", sprintf("Rscript scripts/run_shape_ensemble.R %d", n_lots), "```", "",
  "[Paired records](records.csv), [summary](summary.csv) and [settings](settings.R)",
  "preserve all component comparisons, training likelihoods and model weights.",
  "See [SHAPE_ENSEMBLE.md](../../SHAPE_ENSEMBLE.md) for the model and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "shape_ensemble.png"), width = 1500, height = 780, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 6, 4, 1), mgp = c(4.5, 1, 0))
labels <- c("Equal\nshapes", "Nearby\nshapes", "Different\nshapes")
contrasts <- c("brier_improvement_vs_shared", "ensemble_minus_shared_eur")
for (i in seq_along(contrasts)) {
  prefix <- contrasts[i]
  means <- summary[[paste0(prefix, "_mean")]]
  lower <- summary[[paste0(prefix, "_lower_95")]]
  upper <- summary[[paste0(prefix, "_upper_95")]]
  x <- seq_along(means)
  graphics::plot(x, means, pch = 19, col = "#276a98", xaxt = "n", las = 1,
    ylim = range(c(0, lower, upper)), xlim = c(0.7, 3.3), xlab = "",
    ylab = c("Shared minus ensemble Brier score", "Ensemble minus shared return (EUR per lot)")[i],
    main = c("Future prediction improvement", "Realised return difference")[i])
  graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  nonzero <- upper > lower
  graphics::arrows(x[nonzero], lower[nonzero], x[nonzero], upper[nonzero],
    angle = 90, code = 3, length = 0.05, col = "#276a98")
  graphics::axis(1, x, labels, cex.axis = 0.9)
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d paired records to %s\n", nrow(records), destination))
