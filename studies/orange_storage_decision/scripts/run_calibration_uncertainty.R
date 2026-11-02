# Run from studies/orange_storage_decision:
# Rscript scripts/run_calibration_uncertainty.R [replicates_per_method] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/calibration.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_calibration_uncertainty.R [n_boot] [output_directory]")
n_boot <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 500L
destination <- if (length(args) == 2L) args[2] else "results/calibration_uncertainty"
settings <- list(training_seed = 20261031L, bootstrap_seed = 20261101L,
  n_boot = n_boot, reference_per_class = c(50L, 200L, 1000L),
  sensitivity = 0.9, specificity = 0.9, decision_day = 12L, prediction_day = 20L,
  delivery_lag_days = 2L, storage_eur_per_kg_day = 0.001,
  r_version = R.version.string, rng_kind = RNGkind())
truth <- data.frame(cohort = c("advanced", "intermediate", "initially_immature"),
  mass_kg = c(425, 425, 150), initially_sellable = c(TRUE, TRUE, FALSE),
  shape = c(2, 2, 1), scale = c(20, 35, 1))
inventory <- transform(truth, shape = 1, scale = 1)
inspections <- expand.grid(cohort = c("advanced", "intermediate"), day = c(3L, 6L, 9L, 12L),
  KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
inspections$n_checked <- 180L
index <- match(inspections$cohort, truth$cohort)
probability <- inspection_label_probability(
  weibull_survival(inspections$day, truth$shape[index], truth$scale[index]),
  settings$sensitivity, settings$specificity)
set.seed(settings$training_seed)
inspections$n_acceptable <- stats::rbinom(nrow(inspections), inspections$n_checked, probability)
prices <- expand.grid(cohort = c("advanced", "intermediate"), day = 12:28,
  KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
prices$price_eur_per_kg <- 0.8 + 0.04 * (prices$day - 12)
calibration <- data.frame(reference_per_class = settings$reference_per_class, day = 10L,
  true_positive = 0.9 * settings$reference_per_class,
  false_negative = 0.1 * settings$reference_per_class,
  true_negative = 0.9 * settings$reference_per_class,
  false_positive = 0.1 * settings$reference_per_class)

# Calibration proportions are held fixed by design; only their sample sizes vary.
# Resetting the seed preserves identical training draws across all three cases.
experiments <- lapply(seq_len(nrow(calibration)), function(i) {
  set.seed(settings$bootstrap_seed)
  result <- bootstrap_calibrated_sale(inspections, inventory, prices, calibration[i, ],
    settings$storage_eur_per_kg_day, settings$decision_day,
    settings$delivery_lag_days, settings$prediction_day, settings$n_boot)
  n_reference <- calibration$reference_per_class[i]
  list(draws = cbind(reference_per_class = n_reference, result$draws),
       summary = cbind(reference_per_class = n_reference,
                        summarize_calibration_bootstrap(result$draws)),
       point = cbind(reference_per_class = n_reference, result$point_estimate))
})
draws <- do.call(rbind, lapply(experiments, `[[`, "draws"))
summary <- do.call(rbind, lapply(experiments, `[[`, "summary"))
points <- do.call(rbind, lapply(experiments, `[[`, "point"))
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
tables <- list(draws = draws, summary = summary, point_estimates = points,
  calibration_counts = calibration, reported_inspections = inspections,
  inventory = inventory, generating_truth = truth, prices = prices)
for (name in names(tables)) {
  utils::write.csv(tables[[name]], file.path(destination, paste0(name, ".csv")), row.names = FALSE)
}
writeLines(trimws(capture.output(dput(settings)), which = "right"),
  file.path(destination, "settings.R"), useBytes = TRUE)
lines <- c("# Finite inspection calibration: bootstrap demonstration", "",
  "One synthetic 850-kg eligible lot, with 150 kg of initially immature fruit excluded.",
  "Calibration tables are constructed to have 90% sensitivity and specificity",
  "at every sample size. They are not sampled validation datasets. This isolates",
  "the effect of reference sample size while holding the fitted decision fixed.", "",
  sprintf("Point estimate: sell on day %d; %.1f kg acceptable on fixed day %d.",
    points$sale_day[1], points$acceptable_kg[1], settings$prediction_day), "",
  "## Bootstrap distributions", "",
  sprintf("%d attempts per method and calibration size; percentiles use successful refits.", n_boot),
  "Conditional holds estimated inspection rates fixed. Recalibrated also resamples",
  "independent reference counts and re-estimates the rates before refitting.", "",
  "| Reference fruit per true class | Method | Successful / attempted | Sale day median [2.5%, 97.5%] | Day-20 acceptable kg median [2.5%, 97.5%] | Mass interval width (kg) |",
  "|---:|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %d | %s | %d / %d | %.0f [%.0f, %.0f] | %.1f [%.1f, %.1f] | %.1f |",
    x$reference_per_class, x$method, x$successful, x$attempted,
    x$sale_day_median, x$sale_day_lower_95, x$sale_day_upper_95,
    x$acceptable_kg_median, x$acceptable_kg_lower_95, x$acceptable_kg_upper_95,
    x$acceptable_kg_upper_95 - x$acceptable_kg_lower_95))
}
lines <- c(lines, "", "![Bootstrap mass uncertainty](calibration_uncertainty.png)", "",
  "## Interpretation", "",
  "These distributions describe parameter and decision uncertainty under a fitted",
  "Weibull model and a fixed price path. They are not predictive intervals for",
  "realised fruit mass, confidence sets for an optimal day, or profitability evidence.",
  "Coverage has not been established across independent lots. A larger calibration",
  "sample need not narrow every estimated interval in a finite bootstrap run.", "",
  sprintf("Recorded failures: %d uninformative calibration draws and %d fit failures.",
    sum(summary$calibration_failures), sum(summary$fit_failures)),
  "Failures remain in draws.csv; no replacements are drawn. Failed replicates can",
  "make successful-only percentiles selective. Reference errors, rate drift and",
  "dependence between reference and storage samples are not modeled.", "",
  "The plug-in binomial bootstrap is degenerate when an observed reference class",
  "has no errors or no correct labels. A finite perfect reference sample does not",
  "establish perfect inspection accuracy; boundary cases need another uncertainty method.", "",
  "## Reproduction", "", "```sh",
  sprintf("Rscript scripts/run_calibration_uncertainty.R %d", n_boot), "```", "",
  "[Draws](draws.csv), [summary](summary.csv), [point estimates](point_estimates.csv),",
  "[reference counts](calibration_counts.csv), [reported inspections](reported_inspections.csv),",
  "[inventory](inventory.csv), [generating truth](generating_truth.csv),",
  "[prices](prices.csv) and [settings](settings.R) preserve the complete synthetic example.",
  "See [CALIBRATION.md](../../CALIBRATION.md) for the two-sample bootstrap and data contract.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "calibration_uncertainty.png"), width = 1200, height = 800, res = 140)
graphics::par(mar = c(5, 5, 4, 1))
mass_range <- range(c(summary$acceptable_kg_lower_95, summary$acceptable_kg_upper_95), na.rm = TRUE)
mass_range[2] <- mass_range[2] + 0.2 * diff(mass_range)
graphics::plot(NA, xlim = c(0.7, 3.3),
  ylim = mass_range,
  xlab = "Reference fruit per true class", ylab = "Expected acceptable mass on day 20 (kg)",
  xaxt = "n", las = 1, main = "Accounting for finite calibration samples")
graphics::mtext("Median and central 95% bootstrap range; one synthetic lot", side = 3, line = 0.5, cex = 0.8)
graphics::axis(1, 1:3, settings$reference_per_class)
colors <- c(conditional = "#276a98", recalibrated = "#b34f24")
for (method in names(colors)) {
  part <- summary[summary$method == method, ]
  x <- seq_len(nrow(part)) + if (method == "conditional") -0.08 else 0.08
  graphics::points(x, part$acceptable_kg_median, pch = 19, col = colors[method])
  nonzero <- part$acceptable_kg_upper_95 > part$acceptable_kg_lower_95
  graphics::arrows(x[nonzero], part$acceptable_kg_lower_95[nonzero],
    x[nonzero], part$acceptable_kg_upper_95[nonzero],
    code = 3, angle = 90, length = 0.05, col = colors[method])
}
graphics::legend("topright", legend = c("Conditional", "Recalibrated"),
  col = colors, pch = 19, bty = "n")
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d attempted bootstrap rows to %s\n", nrow(draws), destination))
